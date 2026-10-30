import json
import re
import uuid
from pathlib import Path
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from app.models.deposits import ConditionPhoto, Deposit, Payment
from app.models.marketplace import Conversation, IdentitySubmission, Listing, Message, OwnerApplication, utcnow
from app.models.user import User, UserRole
from app.services.marketplace import redate_sample
DATA = Path(__file__).resolve().parent.parent / "data" / "listings.json"
NAMESPACE = uuid.UUID("6f1c2d3e-0000-4000-8000-7472757374ff")
def _owner_id(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))
FIELDS = ("title", "locality", "city", "pincode", "lat", "lng", "rent", "deposit", "bhk", "furnishing",
          "area_sqft", "amenities", "preferred_tenants", "available_from", "min_months", "max_months")
async def seed_sample_listings(db: AsyncSession) -> int:
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    wanted = {r["id"] for r in rows}
    existing = {x.id: x for x in await db.scalars(select(Listing).where(Listing.listed_days_ago.is_not(None)))}
    owners = {u.id for u in await db.scalars(select(User).where(User.is_demo.is_(True)))}
    for old_id, old in existing.items():
        if old_id in wanted:
            continue
        has_chats = await db.scalar(select(Conversation.id).where(Conversation.listing_id == old_id).limit(1))
        if has_chats:
            old.status = "removed"
        else:
            await db.delete(old)
    added = 0
    for r in rows:
        name = r["landlord"]["name"]
        oid = _owner_id(name)
        if oid not in owners:
            first, _, last = name.partition(" ")
            slug = re.sub(r"[^a-z]+", ".", name.lower()).strip(".")
            db.add(User(id=oid, email=f"{slug}@demo.trustrent.in", name=name, first_name=first, last_name=last,
                        role=UserRole.LANDLORD, is_verified=r["landlord"].get("verified", True), is_demo=True,
                        provider="demo"))
            owners.add(oid)
        listing = existing.get(r["id"])
        if listing is None:
            listing = Listing(id=r["id"], status="live")
            db.add(listing)
            added += 1
        for f in FIELDS:
            setattr(listing, f, r[f])
        listing.owner_id = oid
        listing.show_exact_location = False
        listing.photos = r.get("photos", [])
        listing.description = r.get("description")
        listing.about_owner = r.get("about_owner")
        listing.tenancies_completed = r["landlord"]["tenancies_completed"]
        listing.full_refunds = r["landlord"]["full_refunds"]
        listing.disputes_lost = r["landlord"]["disputes_lost"]
        listing.listed_days_ago = r.get("listed_days_ago", 30)
        if listing.status == "removed":
            listing.status = "live"
        redate_sample(listing)
    await db.commit()
    return added
async def seed_demo_admin(db: AsyncSession) -> None:
    from app.core.config import settings
    from app.services.accounts import hash_secret, verify_secret
    if not settings.DEMO_MODE or not settings.ADMIN_EMAILS or not settings.DEMO_ADMIN_PASSWORD:
        return
    email = settings.ADMIN_EMAILS[0].lower()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        if not verify_secret(settings.DEMO_ADMIN_PASSWORD, existing.password_hash):  # password from .env
            existing.password_hash = hash_secret(settings.DEMO_ADMIN_PASSWORD)
            await db.commit()
        return
    db.add(User(id=str(uuid.uuid4()), email=email, name="TrustRent Admin", first_name="TrustRent", last_name="Admin",
                username="admin", phone="+910000000000", country="India", provider="password",
                password_hash=hash_secret(settings.DEMO_ADMIN_PASSWORD), role=UserRole.TENANT, is_verified=True))
    await db.commit()
DEMO_TENANTS = [
    ("Aditi Joshi", "month", 21),
    ("Rohan Mehta", "quarter", 64),
    ("Neha Patel", None, 0),
]
DEMO_DEPOSITS = [
    ("DEP-DEMO0001", 0, "IND-VN-101", 40, "held"),
    ("DEP-DEMO0002", 1, "IND-PY-201", 120, "proposed"),
    ("DEP-DEMO0003", 2, "IND-VN-103", 380, "settled"),
]
DEMO_CHATS = [
    [(False, "Hi, is this home still available? I'm moving to Indore for work next month."),
     (True, "Yes, it is. You can visit this Saturday after 11 am."),
     (False, "Saturday 11:30 works. Is parking included in the rent?"),
     (True, "Yes, one covered parking spot. See you on Saturday.")],
    [(False, "Hello, is the flat near the lake still free? We are a family of three."),
     (True, "Yes. Families are welcome. Water is 24x7 and there is a lift."),
     (False, "Great. Can we see it on Sunday morning?"),
     (True, "Sunday 10 am is fine. I'll share the exact address after you confirm.")],
    [(False, "Hi, I'd like to rent this for 11 months. Is the deposit negotiable?"),
     (True, "The deposit is two months' rent, held through TrustRent, so it's safe for you."),
     (False, "That works for me. I'll pay it through the app."),
     (True, "Done, I can see the receipt. Welcome!")],
]
async def seed_demo_deposits(db: AsyncSession) -> int:
    from app.services.ledger import record_deposit, record_settlement
    if await db.get(Deposit, DEMO_DEPOSITS[0][0]):
        return 0
    now = utcnow()
    tenants = []
    for name, plan, days_left in DEMO_TENANTS:
        tid = _owner_id("tenant:" + name)
        t = await db.get(User, tid)
        if t is None:
            first, _, last = name.partition(" ")
            slug = re.sub(r"[^a-z]+", ".", name.lower()).strip(".")
            t = User(id=tid, email=f"{slug}@demo.trustrent.in", name=name, first_name=first, last_name=last,
                     username=slug.replace(".", "_")[:20], role=UserRole.TENANT, is_verified=True, is_demo=True,
                     provider="demo", country="India", created_at=now - timedelta(days=400))
            db.add(t)
        if plan:
            from app.api.v1.accounts import PLANS
            total, price = PLANS[plan]
            t.premium_plan, t.premium_until = plan, now + timedelta(days=days_left)
            db.add(Payment(id=str(uuid.uuid5(NAMESPACE, "premium:" + name)), user_id=tid, purpose="premium", ref=plan,
                           amount=price, provider="demo", order_id=f"demo_premium_{tid[:8]}", status="paid",
                           paid_at=now - timedelta(days=total - days_left)))
        tenants.append(t)
    await db.flush()
    added = 0
    for dep_id, ti, listing_id, ago, outcome in DEMO_DEPOSITS:
        listing = await db.get(Listing, listing_id)
        if not listing:
            continue
        tenant, paid = tenants[ti], now - timedelta(days=ago)
        pay = Payment(id=str(uuid.uuid5(NAMESPACE, "deposit:" + dep_id)), user_id=tenant.id, purpose="deposit",
                      ref=listing_id, amount=listing.deposit, provider="demo", order_id=f"demo_{dep_id.lower()}",
                      status="paid", created_at=paid, paid_at=paid)
        db.add(pay)
        d = Deposit(id=dep_id, listing_id=listing_id, tenant_id=tenant.id, owner_id=listing.owner_id,
                    amount=listing.deposit, payment_id=pay.id, status="held", paid_at=paid)
        db.add(d)
        await db.flush()
        await record_deposit(db, d)
        if outcome in ("proposed", "settled"):
            d.deducted = 3500 if outcome == "proposed" else 6000
            d.refunded = d.amount - d.deducted
            d.deduction_reason = ("Repainting one bedroom wall (marks from furniture)" if outcome == "proposed"
                                  else "Broken geyser replaced and two weeks of unpaid electricity")
            d.proposed_by, d.proposed_at, d.status = listing.owner_id, now - timedelta(days=2), "settlement_proposed"
        if outcome == "settled":
            d.settled_at, d.settled_by, d.status = now - timedelta(days=12), tenant.id, "settled"
            d.refund_ref, d.owner_payout = "demo-refund", "paid"
            await record_settlement(db, d)
        conv = Conversation(id=str(uuid.uuid5(NAMESPACE, "chat:" + dep_id)), listing_id=listing_id, seeker_id=tenant.id,
                            owner_id=listing.owner_id, created_at=paid - timedelta(days=6), updated_at=paid - timedelta(days=5))
        db.add(conv)
        script = DEMO_CHATS[DEMO_DEPOSITS.index((dep_id, ti, listing_id, ago, outcome))]
        for i, (by_owner, text) in enumerate(script):
            who = listing.owner_id if by_owner else tenant.id
            db.add(Message(id=str(uuid.uuid5(NAMESPACE, f"msg:{dep_id}:{i}")), conversation_id=conv.id, sender_id=who,
                           kind="text", text=text, created_at=paid - timedelta(days=6, hours=-i)))
        added += 1
    await db.commit()
    return added
async def remove_sample_data(db: AsyncSession) -> int:  # sample cleanup
    demo = list(await db.scalars(select(User.id).where(User.is_demo.is_(True))))
    homes = list(await db.scalars(select(Listing.id).where(or_(Listing.owner_id.in_(demo), Listing.listed_days_ago.is_not(None)))))
    if not demo and not homes:
        return 0
    deps = list(await db.scalars(select(Deposit.id).where(or_(Deposit.listing_id.in_(homes), Deposit.tenant_id.in_(demo),
                                                              Deposit.owner_id.in_(demo)))))
    pays = list(await db.scalars(select(Deposit.payment_id).where(Deposit.id.in_(deps))))
    chats = list(await db.scalars(select(Conversation.id).where(or_(Conversation.listing_id.in_(homes),
                                                                    Conversation.seeker_id.in_(demo), Conversation.owner_id.in_(demo)))))
    await db.execute(delete(Message).where(or_(Message.conversation_id.in_(chats), Message.sender_id.in_(demo))))
    await db.execute(delete(Conversation).where(Conversation.id.in_(chats)))
    await db.execute(delete(ConditionPhoto).where(ConditionPhoto.deposit_id.in_(deps)))
    await db.execute(delete(Deposit).where(Deposit.id.in_(deps)))
    await db.execute(delete(Payment).where(or_(Payment.id.in_(pays), Payment.user_id.in_(demo))))
    await db.execute(delete(Listing).where(Listing.id.in_(homes)))
    await db.execute(delete(OwnerApplication).where(OwnerApplication.user_id.in_(demo)))
    await db.execute(delete(IdentitySubmission).where(IdentitySubmission.user_id.in_(demo)))
    await db.execute(delete(User).where(User.id.in_(demo)))
    await db.commit()
    return len(demo) + len(homes)