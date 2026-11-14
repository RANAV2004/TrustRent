import html
import re
import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.errors import field_error
from app.core.ratelimit import client_ip
from app.models.deposits import Deposit
from app.models.extras import Agreement, AgreementSignature
from app.models.marketplace import Listing, utcnow
from app.models.user import User
from app.services.accounts import display_name, iso, is_reviewer
from app.services.hash_service import HashService
from app.services.ledger import record_event
from app.services.notify import notify
from app.core.config import settings

router = APIRouter(tags=["Rent agreements"])
LEGAL_NOTE = ("This agreement was signed electronically on TrustRent by typed name. TrustRent records who signed, when, "
              "and a fingerprint of the exact text. It is not an Aadhaar eSign or digital-signature-certificate signature. "
              "Where state law requires stamp duty or registration (for example, leases of 12 months or more), print this "
              "agreement and stamp or register it as required.")


class TermsIn(BaseModel):
    startDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    months: int = Field(ge=1, le=60)
    monthlyRent: int = Field(ge=1, le=10_000_000)
    rentDueDay: int = Field(default=5, ge=1, le=28)
    noticeDays: int = Field(default=30, ge=0, le=180)
    lockInMonths: int = Field(default=0, ge=0, le=60)
    maintenance: str = Field(default="", max_length=200)
    extraClauses: str = Field(default="", max_length=4000)


class SignIn(BaseModel):
    typedName: str = Field(min_length=2, max_length=160)
    agree: bool


async def _context(db: AsyncSession, deposit_id: str, user: User) -> tuple[Deposit, Listing | None, User, User]:
    d = await db.get(Deposit, deposit_id.strip().upper())
    if not d or (user.id not in (d.tenant_id, d.owner_id) and not is_reviewer(user)):
        raise HTTPException(status_code=404, detail="Deposit not found")
    return d, await db.get(Listing, d.listing_id), await db.get(User, d.tenant_id), await db.get(User, d.owner_id)


def render_text(t: dict, d: Deposit, listing: Listing | None, tenant: User, owner: User) -> str:
    area = f"{listing.locality}, {listing.city} {listing.pincode}" if listing else ""
    address = (f"{listing.address}, {area}" if listing.address else area) if listing else "the property"
    lines = [
        "RESIDENTIAL RENT AGREEMENT",
        f"Agreement for deposit {d.id} on TrustRent.",
        f"Owner (Licensor): {display_name(owner)}, TrustRent user {owner.id}.",
        f"Tenant (Licensee): {display_name(tenant)}, TrustRent user {tenant.id}.",
        f"Property: {address}{f' (TrustRent listing {listing.id})' if listing else ''}.",
        f"1. Term. {t['months']} months starting {t['startDate']}.",
        f"2. Rent. Rs {t['monthlyRent']:,} per month, due by day {t['rentDueDay']} of each month.",
        f"3. Security deposit. Rs {d.amount:,}, paid through TrustRent (deposit {d.id}).",
        "4. Deposit return. At move-out the owner proposes any deduction with a reason within "
        f"{settings.MOVE_OUT_CLAIM_DAYS} days, or the full deposit is refunded. The tenant accepts or disputes within "
        f"{settings.SETTLEMENT_RESPONSE_DAYS} days, or the proposal is accepted. Disputes are decided by a TrustRent reviewer "
        "using the move-in and move-out photos and both parties' statements.",
        f"5. Notice. Either party gives {t['noticeDays']} days' written notice to end the agreement."
        + (f" Lock-in: {t['lockInMonths']} months." if t["lockInMonths"] else ""),
    ]
    if t.get("maintenance"):
        lines.append(f"6. Maintenance and utilities. {t['maintenance']}")
    if t.get("extraClauses"):
        lines.append("7. Other terms. " + t["extraClauses"])
    lines.append(LEGAL_NOTE)
    return "\n\n".join(lines)


async def _out(db: AsyncSession, a: Agreement | None, d: Deposit, user: User) -> dict:
    if not a:
        return {"agreement": None, "canCreate": user.id == d.owner_id and d.status not in ("settled", "settling")}
    sigs = list(await db.scalars(select(AgreementSignature).where(AgreementSignature.agreement_id == a.id).order_by(AgreementSignature.signed_at)))
    text_ok = HashService.hash_text(a.text) == a.text_hash
    roles = {s.role for s in sigs}
    me = "tenant" if user.id == d.tenant_id else "owner" if user.id == d.owner_id else None
    return {
        "agreement": {
            "id": a.id, "terms": a.terms, "text": a.text, "textHash": a.text_hash, "createdAt": iso(a.created_at),
            "status": "signed" if roles >= {"tenant", "owner"} else "partly_signed" if sigs else "draft",
            "verified": text_ok and all(s.text_hash == a.text_hash for s in sigs),
            "signatures": [{"role": s.role, "typedName": s.typed_name, "signedAt": iso(s.signed_at), "textHash": s.text_hash,
                            "receipt": s.record_tx} for s in sigs],
        },
        "canCreate": user.id == d.owner_id and not sigs and d.status not in ("settled", "settling"),
        "canSign": bool(me) and me not in roles,
        "signAs": display_name(user) if me else None,
    }


@router.get("/deposits/{deposit_id}/agreement")  # agreement
async def get_agreement(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, *_ = await _context(db, deposit_id, user)
    return await _out(db, await db.scalar(select(Agreement).where(Agreement.deposit_id == d.id)), d, user)


@router.post("/deposits/{deposit_id}/agreement", status_code=201)  # owner drafts
async def create_agreement(deposit_id: str, body: TermsIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, listing, tenant, owner = await _context(db, deposit_id, user)
    if user.id != d.owner_id:
        raise HTTPException(status_code=403, detail="Only the owner drafts the agreement")
    if d.status in ("settled", "settling"):
        raise field_error("This deposit is settled.", None, status.HTTP_409_CONFLICT)
    try:
        date.fromisoformat(body.startDate)
    except ValueError:
        raise field_error("Enter a real start date.", "startDate") from None
    if body.lockInMonths > body.months:
        raise field_error("The lock-in can't be longer than the agreement.", "lockInMonths")
    a = await db.scalar(select(Agreement).where(Agreement.deposit_id == d.id))
    if a and await db.scalar(select(AgreementSignature.id).where(AgreementSignature.agreement_id == a.id).limit(1)):
        raise field_error("Someone already signed this agreement, so it can't be changed.", None, status.HTTP_409_CONFLICT)
    terms = body.model_dump()
    terms["maintenance"] = re.sub(r"\s+", " ", terms["maintenance"]).strip()
    terms["extraClauses"] = terms["extraClauses"].strip()
    text = render_text(terms, d, listing, tenant, owner)
    if not a:
        a = Agreement(id=str(uuid.uuid4()), deposit_id=d.id, created_by=user.id)
        db.add(a)
    a.terms, a.text, a.text_hash, a.created_at = terms, text, HashService.hash_text(text), utcnow()
    await db.flush()
    a.record_tx = (await record_event(db, d.id, "agreement", {"agreementId": a.id, "textHash": a.text_hash})).entry_hash
    await db.commit()
    notify(tenant, f"Rent agreement ready to sign ({d.id})",
           [f"{display_name(owner)} drafted the rent agreement for your home. Read it and sign it on TrustRent."], "/deposits")
    return await _out(db, a, d, user)


@router.post("/deposits/{deposit_id}/agreement/sign")  # e-sign
async def sign_agreement(deposit_id: str, body: SignIn, request: Request, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    d, listing, tenant, owner = await _context(db, deposit_id, user)
    role = "tenant" if user.id == d.tenant_id else "owner" if user.id == d.owner_id else None
    if not role:
        raise HTTPException(status_code=403, detail="Only the tenant and the owner sign")
    a = await db.scalar(select(Agreement).where(Agreement.deposit_id == d.id))
    if not a:
        raise HTTPException(status_code=404, detail="No agreement yet")
    if not body.agree:
        raise field_error("Tick the box to confirm you agree to every term.", "agree")
    if " ".join(body.typedName.lower().split()) != " ".join(display_name(user).lower().split()):
        raise field_error(f"Type your full name exactly as on your account: {display_name(user)}", "typedName")
    if HashService.hash_text(a.text) != a.text_hash:
        raise field_error("This agreement's text doesn't match its fingerprint. Contact support.", None, status.HTTP_409_CONFLICT)
    if await db.scalar(select(AgreementSignature.id).where(AgreementSignature.agreement_id == a.id, AgreementSignature.role == role)):
        raise field_error("You already signed this agreement.", None, status.HTTP_409_CONFLICT)
    sig = AgreementSignature(id=str(uuid.uuid4()), agreement_id=a.id, user_id=user.id, role=role, typed_name=body.typedName.strip(),
                             text_hash=a.text_hash, ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300],
                             signed_at=utcnow())
    db.add(sig)
    await db.flush()
    sig.record_tx = (await record_event(db, d.id, "signature", {"agreementId": a.id, "role": role, "userId": user.id,
                                                               "textHash": a.text_hash, "signedAt": iso(sig.signed_at)})).entry_hash
    await db.commit()
    other = owner if role == "tenant" else tenant
    notify(other, f"Rent agreement signed by the {role} ({d.id})",
           [f"{display_name(user)} signed the rent agreement." + (" It still needs your signature." if other else "")], "/deposits")
    return await _out(db, a, d, user)


@router.get("/deposits/{deposit_id}/agreement/document")  # printable copy
async def agreement_document(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, *_ = await _context(db, deposit_id, user)
    a = await db.scalar(select(Agreement).where(Agreement.deposit_id == d.id))
    if not a:
        raise HTTPException(status_code=404, detail="No agreement yet")
    sigs = list(await db.scalars(select(AgreementSignature).where(AgreementSignature.agreement_id == a.id)))
    body = "".join(f"<p>{html.escape(p)}</p>" for p in a.text.split("\n\n"))
    signed = "".join(f"<li>{html.escape(s.role.title())}: <strong>{html.escape(s.typed_name)}</strong>, signed {html.escape(iso(s.signed_at) or '')}</li>"
                     for s in sigs) or "<li>Not signed yet</li>"
    page = (f"<!doctype html><html><head><meta charset='utf-8'><title>Rent agreement {html.escape(d.id)}</title>"
            "<style>body{font-family:Georgia,serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.55}"
            "code{word-break:break-all}</style></head><body>"
            f"{body}<h3>Signatures</h3><ul>{signed}</ul><p>Text fingerprint (SHA-256): <code>{html.escape(a.text_hash)}</code></p></body></html>")
    return Response(page, media_type="text/html", headers={
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "Cache-Control": "no-store",
        "Content-Disposition": f'inline; filename="rent-agreement-{d.id}.html"'})
