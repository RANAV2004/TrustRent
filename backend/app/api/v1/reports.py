import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.admin import require_admin
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import field_error
from app.core.ratelimit import enforce
from app.models.marketplace import Listing, utcnow
from app.models.trust import AuditLog, ListingReport
from app.models.user import User
from app.services.accounts import display_name, is_admin, iso
from app.services.audit import audit
from app.services.notify import notify

router = APIRouter(tags=["Reports and audit"])
REASONS = {"fake": "Fake or not real", "scam": "Asks for money outside TrustRent", "wrong_details": "Wrong price, photos or details",
           "already_rented": "Already rented", "offensive": "Offensive or discriminatory", "other": "Something else"}
HELD_NOTE = "Paused while TrustRent checks reports about this home."


class ReportIn(BaseModel):
    reason: str
    details: str = Field(default="", max_length=1000)


class ResolveIn(BaseModel):
    action: str  # dismiss | unlist
    note: str = Field(default="", max_length=300)


@router.get("/reports/reasons")
async def reasons():
    return [{"id": k, "label": v} for k, v in REASONS.items()]


@router.post("/listings/{listing_id}/report", status_code=201)  # report a home
async def report_listing(listing_id: str, body: ReportIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, listing_id)
    if not listing or listing.status in ("removed",):
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.owner_id == user.id:
        raise field_error("You can't report your own home.", None)
    if body.reason not in REASONS:
        raise field_error("Choose a reason.", "reason")
    if body.reason == "other" and len(body.details.strip()) < 10:
        raise field_error("Tell us what's wrong in a sentence.", "details")
    enforce(f"report:user:{user.id}", 10, 86400, "You've sent a lot of reports today. Try again tomorrow.")
    if await db.scalar(select(ListingReport.id).where(ListingReport.listing_id == listing.id, ListingReport.reporter_id == user.id,
                                                    ListingReport.status == "open")):
        raise field_error("You've already reported this home. We're looking into it.", None, status.HTTP_409_CONFLICT)
    db.add(ListingReport(id=str(uuid.uuid4()), listing_id=listing.id, reporter_id=user.id, reason=body.reason,
                         details=body.details.strip() or None, created_at=utcnow()))
    await db.flush()
    reporters = await db.scalar(select(func.count(func.distinct(ListingReport.reporter_id))).where(
        ListingReport.listing_id == listing.id, ListingReport.status == "open"))
    held = False
    if (reporters or 0) >= settings.REPORTS_TO_HOLD_LISTING and listing.status == "live":
        listing.status, listing.admin_note, held = "review", HELD_NOTE, True
        audit(db, None, "listing.held_for_reports", "listing", listing.id, reporters=reporters)
    await db.commit()
    admins = [e.lower() for e in settings.ADMIN_EMAILS]
    for staff in await db.scalars(select(User).where(func.lower(User.email).in_(admins), User.deleted_at.is_(None))):
        if is_admin(staff):
            notify(staff, f"Listing reported: {listing.title}", [f"Reason: {REASONS[body.reason]}",
                   "It was paused for review automatically." if held else f"Open reports: {reporters}"], "/admin/reports")
    return {"ok": True, "message": "Thanks. TrustRent will check this home."}


def _report_out(r: ListingReport, listing: Listing | None, reporter: User | None, open_count: int) -> dict:
    return {"id": r.id, "reason": r.reason, "reasonLabel": REASONS.get(r.reason, r.reason), "details": r.details,
            "status": r.status, "createdAt": iso(r.created_at), "resolvedAt": iso(r.resolved_at), "resolution": r.resolution,
            "reporter": {"id": r.reporter_id, "name": display_name(reporter) if reporter else ""},
            "listing": {"id": r.listing_id, "title": listing.title if listing else "", "status": listing.status if listing else "",
                        "ownerId": listing.owner_id if listing else None, "openReports": open_count}}


@router.get("/admin/reports")  # report queue
async def list_reports(state: str = "open", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    q = select(ListingReport).order_by(ListingReport.created_at.desc())
    if state != "all":
        q = q.where(ListingReport.status == state)
    rows = list(await db.scalars(q.limit(500)))
    listings = {x.id: x for x in await db.scalars(select(Listing).where(Listing.id.in_({r.listing_id for r in rows})))} if rows else {}
    people = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({r.reporter_id for r in rows})))} if rows else {}
    counts = dict((await db.execute(select(ListingReport.listing_id, func.count()).where(ListingReport.status == "open")
                                    .group_by(ListingReport.listing_id))).all())
    return [_report_out(r, listings.get(r.listing_id), people.get(r.reporter_id), counts.get(r.listing_id, 0)) for r in rows]


@router.post("/admin/reports/{report_id}/resolve")  # act on a report
async def resolve(report_id: str, body: ResolveIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(ListingReport, report_id)
    if not r or r.status != "open":
        raise HTTPException(status_code=404, detail="Open report not found")
    if body.action not in ("dismiss", "unlist"):
        raise field_error("Choose dismiss or unlist.", "action")
    listing = await db.get(Listing, r.listing_id)
    now = utcnow()
    if body.action == "unlist":
        if listing and listing.status != "removed":
            listing.status, listing.admin_note = "blocked", body.note.strip() or f"Reported: {REASONS.get(r.reason, r.reason)}"
        for other in await db.scalars(select(ListingReport).where(ListingReport.listing_id == r.listing_id, ListingReport.status == "open")):
            other.status, other.resolved_by, other.resolved_at, other.resolution = "actioned", admin.id, now, body.note.strip() or "Home unlisted"
        audit(db, admin, "report.unlisted", "listing", r.listing_id, report=r.id, note=body.note.strip() or None)
    else:
        r.status, r.resolved_by, r.resolved_at, r.resolution = "dismissed", admin.id, now, body.note.strip() or "No problem found"
        await db.flush()
        left = await db.scalar(select(func.count()).select_from(ListingReport).where(
            ListingReport.listing_id == r.listing_id, ListingReport.status == "open"))
        if listing and listing.status == "review" and listing.admin_note == HELD_NOTE and not left:
            listing.status, listing.admin_note = "live", None  # all reports cleared: back online
        audit(db, admin, "report.dismissed", "listing", r.listing_id, report=r.id, note=body.note.strip() or None)
    await db.commit()
    if body.action == "unlist" and listing:
        notify(await db.get(User, listing.owner_id), f"{listing.title} was unlisted",
               [f"TrustRent unlisted your home after a report: {listing.admin_note}", "Contact support if you think this is a mistake."], "/owner")
    return _report_out(r, listing, await db.get(User, r.reporter_id), 0)


@router.get("/admin/audit")  # audit log
async def audit_log(action: str = "", actor: str = "", target: str = "", page: int = Query(1, ge=1), pageSize: int = Query(50, ge=1, le=200),
                    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.like(f"{action}%"))
    if actor:
        q = q.where(func.lower(AuditLog.actor_label).like(f"%{actor.lower()}%"))
    if target:
        q = q.where(AuditLog.target_id == target)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = list(await db.scalars(q.order_by(AuditLog.id.desc()).offset((page - 1) * pageSize).limit(pageSize)))
    actions = sorted(set(await db.scalars(select(AuditLog.action).distinct())))
    return {"total": total, "page": page, "actions": actions,
            "rows": [{"id": a.id, "at": iso(a.at), "actor": a.actor_label, "action": a.action, "targetType": a.target_type,
                      "targetId": a.target_id, "details": a.details or {}, "ip": a.ip} for a in rows]}
