import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.admin import require_admin
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.errors import field_error
from app.models.deposits import Deposit
from app.models.marketplace import utcnow
from app.models.trust import Review
from app.models.user import User
from app.services.accounts import display_name, iso
from app.services.audit import audit
from app.services.notify import notify
from app.services.reviews import rating_summary, visible_reviews, window_end

router = APIRouter(tags=["Reviews"])


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=1000)


class HideIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def review_out(r: Review, author: User | None) -> dict:
    return {"id": r.id, "rating": r.rating, "text": r.text, "createdAt": iso(r.created_at),
            "direction": r.direction, "author": display_name(author) if author else "", "depositId": r.deposit_id}


async def _deposit(db: AsyncSession, deposit_id: str, user: User) -> Deposit:
    d = await db.get(Deposit, deposit_id.strip().upper())
    if not d or user.id not in (d.tenant_id, d.owner_id):
        raise HTTPException(status_code=404, detail="Deposit not found")
    return d


@router.get("/deposits/{deposit_id}/review")  # my review for a tenancy
async def my_review(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    other_id = d.owner_id if user.id == d.tenant_id else d.tenant_id
    mine = await db.scalar(select(Review).where(Review.deposit_id == d.id, Review.author_id == user.id))
    theirs = await db.scalar(select(Review).where(Review.deposit_id == d.id, Review.author_id == other_id))
    end = window_end(d)
    open_ = d.status == "settled" and end is not None and end > utcnow()
    visible = theirs if theirs and (mine or not open_) and not theirs.hidden_at else None
    other = await db.get(User, other_id)
    return {"canReview": open_ and mine is None, "reviewBy": iso(end) if d.status == "settled" else None,
            "about": display_name(other) if other else "", "mine": review_out(mine, user) if mine else None,
            "theirs": review_out(visible, other) if visible else None, "theirsWaiting": bool(theirs and not visible)}


@router.post("/deposits/{deposit_id}/review", status_code=201)  # leave a review
async def leave_review(deposit_id: str, body: ReviewIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    if d.status != "settled":
        raise field_error("You can review once the deposit is settled.", None, status.HTTP_409_CONFLICT)
    end = window_end(d)
    if not end or end < utcnow():
        raise field_error("The time to review this tenancy has ended.", None, status.HTTP_409_CONFLICT)
    if await db.scalar(select(Review.id).where(Review.deposit_id == d.id, Review.author_id == user.id)):
        raise field_error("You already reviewed this tenancy.", None, status.HTTP_409_CONFLICT)
    tenant = user.id == d.tenant_id
    subject = d.owner_id if tenant else d.tenant_id
    db.add(Review(id=str(uuid.uuid4()), deposit_id=d.id, author_id=user.id, subject_id=subject,
                  direction="tenant_to_owner" if tenant else "owner_to_tenant", rating=body.rating,
                  text=body.text.strip() or None, created_at=utcnow()))
    await db.commit()
    other = await db.get(User, subject)
    notify(other, "You have a new review", [f"{display_name(user)} reviewed your tenancy ({d.id}).",
           "Reviews stay hidden until you add yours too, or the review period ends."], "/deposits")
    return await my_review(deposit_id, user, db)


@router.get("/users/{user_id}/reviews")  # public reviews about someone
async def user_reviews(user_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = sorted(await visible_reviews(db, {user_id}), key=lambda r: r.created_at, reverse=True)
    authors = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({r.author_id for r in rows})))} if rows else {}
    summary = (await rating_summary(db, {user_id}))[user_id]
    return {"summary": summary, "reviews": [review_out(r, authors.get(r.author_id)) for r in rows[:50]]}


@router.get("/admin/reviews")
async def admin_reviews(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(Review).order_by(Review.created_at.desc()).limit(300)))
    people = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({r.author_id for r in rows} | {r.subject_id for r in rows})))} if rows else {}
    return [review_out(r, people.get(r.author_id)) | {"about": display_name(people[r.subject_id]) if r.subject_id in people else "",
                                                       "hidden": bool(r.hidden_at), "hiddenReason": r.hidden_reason} for r in rows]


@router.post("/admin/reviews/{review_id}/hide")  # moderation
async def hide_review(review_id: str, body: HideIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(Review, review_id)
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    r.hidden_at, r.hidden_reason = utcnow(), body.reason.strip()
    audit(db, admin, "review.hidden", "review", r.id, reason=r.hidden_reason, deposit=r.deposit_id)
    await db.commit()
    return {"ok": True}
