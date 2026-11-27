"""Lawyers: verified sign-up, the owners' lawyer directory, owner-lawyer chats and agreement PDFs.

Flow: a lawyer applies from the sign-in page (no account yet) -> an admin checks the documents and
approves -> TrustRent creates the account and issues a username and temporary password -> the lawyer
signs in, sets their own password and sees owners' messages -> the lawyer uploads the agreement PDF ->
the owner downloads it and can share it with a tenant they know through TrustRent.
"""
import re
import secrets
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import (
    DOC_HINT, ID_DOC_TYPES, MAX_DOC_BYTES, _email, field_error, is_document, read_limited, valid_name,
)
from app.api.v1.admin import _file_response, require_admin, require_full_admin
from app.api.v1.auth import get_current_user
from app.api.v1.condition import clean_image
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import LAWYER_APPLICATIONS_PER_IP, client_ip
from app.models.deposits import Deposit
from app.models.legal import Agreement, AgreementShare, LawyerApplication, LegalCase, LegalMessage
from app.models.marketplace import Conversation, Listing, utcnow
from app.models.user import User, UserRole
from app.services.accounts import account_type, admin_unlocked, display_name, hash_secret, is_admin, iso, normalise_phone
from app.services.files import content_disposition, private_storage, read_private, save_public
from app.services.hash_service import HashService
from app.services.mailer import (
    EmailError, build_lawyer_approved_email, build_lawyer_rejected_email, email_enabled,
)
from app.services.marketplace import media_url
from app.services.notify import notify, notify_admins, recently_active, snippet

router = APIRouter(tags=["Lawyers and agreements"])

PRACTICE_AREAS = [
    "Rental and lease agreements", "Property and real estate", "Tenancy disputes", "Property registration",
    "Civil law", "Consumer law", "Documentation and drafting",
]
ENROLMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/.\- ]{3,39}$")
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 15 * 1024 * 1024
UNAVAILABLE = "This lawyer is no longer available on TrustRent."


# ---------- helpers ----------

def _text(value: str, field: str, label: str, lo: int, hi: int) -> str:
    v = (value or "").strip()
    if not lo <= len(v) <= hi:
        raise field_error(f"Enter {label} ({lo} to {hi} characters).", field)
    return v


def _active_lawyer(u: User | None) -> bool:
    return bool(u and u.is_lawyer and not u.banned_at and not u.deleted_at)


def _safe_name(name: str | None, fallback: str) -> str:
    return "".join(c for c in (name or "") if c.isalnum() or c in "._- ")[:100] or fallback


def application_out(a: LawyerApplication, base_url: str = "") -> dict:
    return {
        "reference": a.id, "status": a.status, "fullName": a.full_name, "email": a.email, "phone": a.phone,
        "city": a.city, "barCouncil": a.bar_council, "enrolmentNo": a.enrolment_no,
        "experienceYears": a.experience_years, "practiceAreas": a.practice_areas or [], "languages": a.languages or [],
        "officeAddress": a.office_address, "about": a.about or "", "idDocType": a.id_doc_type,
        "idFileName": a.id_file_name, "enrolmentFileName": a.enrolment_file_name,
        "idFileHash": a.id_file_hash, "enrolmentFileHash": a.enrolment_file_hash,
        "photo": media_url(base_url, a.public_photo) if a.public_photo and base_url else None,
        "userId": a.user_id, "submittedAt": iso(a.submitted_at), "reviewedAt": iso(a.reviewed_at),
        "reviewNote": a.review_note,
    }


def lawyer_card(a: LawyerApplication, u: User, base_url: str) -> dict:
    return {
        "id": u.id, "name": display_name(u), "photo": media_url(base_url, a.public_photo) if a.public_photo else None,
        "city": a.city, "barCouncil": a.bar_council, "enrolmentNo": a.enrolment_no,
        "experienceYears": a.experience_years, "practiceAreas": a.practice_areas or [], "languages": a.languages or [],
        "phone": u.phone or a.phone, "email": u.email, "officeAddress": a.office_address, "about": a.about or "",
    }


async def _new_username(db: AsyncSession, full_name: str) -> str:
    stem = re.sub(r"[^a-z]", "", full_name.lower().split(" ")[0])[:10] or "lawyer"
    while True:
        candidate = f"adv_{stem}{secrets.randbelow(10_000):04d}"
        if not await db.scalar(select(User.id).where(func.lower(User.username) == candidate)):
            return candidate


def _temp_password() -> str:  # easy to read out on the phone: no 0/O, 1/l/I
    letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    chars = [secrets.choice(letters) for _ in range(8)] + [secrets.choice(digits) for _ in range(3)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


async def _email_quietly(msg) -> bool:
    if not email_enabled():
        return False
    try:
        from app.services import mailer
        await mailer.send_message_email(msg)
        return True
    except EmailError:
        return False


async def _identity_taken(db: AsyncSession, email: str, phone: str, skip_application: str | None = None) -> tuple[str, str] | None:
    if email in {e.lower() for e in settings.ADMIN_EMAILS} or await db.scalar(select(User.id).where(func.lower(User.email) == email)):
        return "email", "A TrustRent account already uses this email. Use another email for your lawyer account."
    if await db.scalar(select(User.id).where(User.phone == phone)):
        return "phone", "A TrustRent account already uses this phone number."
    pending = select(LawyerApplication.id).where(func.lower(LawyerApplication.email) == email, LawyerApplication.status == "pending")
    if skip_application:
        pending = pending.where(LawyerApplication.id != skip_application)
    if await db.scalar(pending):
        return "email", "An application with this email is already waiting for review."
    return None


# ---------- applying (no account yet) ----------

@router.get("/lawyers/options")  # form choices
async def options():
    return {"practiceAreas": PRACTICE_AREAS, "idDocTypes": sorted(ID_DOC_TYPES)}


@router.post("/lawyers/applications", status_code=201)  # lawyer applies
async def apply(
    request: Request,
    fullName: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    city: str = Form(...),
    barCouncil: str = Form(...),
    enrolmentNo: str = Form(...),
    experienceYears: int = Form(...),
    practiceAreas: list[str] = Form(...),
    languages: str = Form(""),
    officeAddress: str = Form(...),
    about: str = Form(""),
    idDocType: str = Form(...),
    photo: UploadFile = File(...),
    idProof: UploadFile = File(...),
    enrolmentCertificate: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    name = _text(fullName, "fullName", "your full name", 3, 120)
    if len(name.split()) < 2 or not valid_name(name):
        raise field_error("Enter your first name and surname, in letters.", "fullName")
    try:
        mail = str(_email.validate_python(email.strip())).lower()
    except ValidationError:
        raise field_error("Enter a valid email address.", "email") from None
    tel = normalise_phone(phone)
    if not 11 <= len(tel) <= 16:
        raise field_error("Enter a valid phone number with country code.", "phone")
    town = _text(city, "city", "the city you practise in", 2, 60)
    council = _text(barCouncil, "barCouncil", "your State Bar Council", 3, 80)
    enrolment = enrolmentNo.strip().upper()
    if not ENROLMENT_RE.match(enrolment):
        raise field_error("Enter your Bar Council enrolment number, e.g. MP/1234/2015.", "enrolmentNo")
    if not 0 <= experienceYears <= 60:
        raise field_error("Enter your years of practice (0 to 60).", "experienceYears")
    areas = [a for a in dict.fromkeys(practiceAreas) if a]
    if not areas or set(areas) - set(PRACTICE_AREAS):
        raise field_error("Choose at least one practice area from the list.", "practiceAreas")
    langs = [x.strip() for x in languages.split(",") if x.strip()]
    if len(langs) > 8 or any(len(x) > 30 for x in langs):
        raise field_error("List up to 8 languages, separated by commas.", "languages")
    office = _text(officeAddress, "officeAddress", "your office address", 10, 300)
    bio = about.strip()
    if len(bio) > 1000:
        raise field_error("Keep the introduction under 1000 characters.", "about")
    if idDocType not in ID_DOC_TYPES:
        raise field_error("Choose a supported ID document.", "idDocType")
    ip = client_ip(request)
    if LAWYER_APPLICATIONS_PER_IP.blocked(ip):
        raise field_error("Too many applications were sent from your network. Try again in an hour.", None,
                          status.HTTP_429_TOO_MANY_REQUESTS)
    taken = await _identity_taken(db, mail, tel)
    if taken:
        raise field_error(taken[1], taken[0], status.HTTP_409_CONFLICT)
    if await db.scalar(select(LawyerApplication.id).where(func.upper(LawyerApplication.enrolment_no) == enrolment,
                                                          LawyerApplication.status.in_(("pending", "approved")))):
        raise field_error("This enrolment number is already registered or waiting for review.", "enrolmentNo",
                          status.HTTP_409_CONFLICT)
    raw_photo = await read_limited(photo, MAX_PHOTO_BYTES, "photo", "The photo is larger than 5 MB.")
    try:
        clean_photo = clean_image(raw_photo)  # also strips location data from the photo
    except HTTPException:
        raise field_error("Your photo must be a JPG, PNG or WebP image.", "photo") from None
    id_bytes = await read_limited(idProof, MAX_DOC_BYTES, "idProof", "The ID document is larger than 10 MB.")
    cert_bytes = await read_limited(enrolmentCertificate, MAX_DOC_BYTES, "enrolmentCertificate",
                                    "The enrolment certificate is larger than 10 MB.")
    if not id_bytes:
        raise field_error("Upload a photo or scan of your ID.", "idProof")
    if not cert_bytes:
        raise field_error("Upload your Bar Council enrolment certificate or ID card.", "enrolmentCertificate")
    if not is_document(id_bytes):
        raise field_error(DOC_HINT, "idProof")
    if not is_document(cert_bytes):
        raise field_error(DOC_HINT, "enrolmentCertificate")
    ref = f"LAW-{uuid.uuid4().hex[:8].upper()}"
    store = private_storage()
    photo_path, photo_iv = store.store(f"lawyer_photo_{ref}", clean_photo)
    id_path, id_iv = store.store(f"lawyer_id_{ref}", id_bytes)
    cert_path, cert_iv = store.store(f"lawyer_enrolment_{ref}", cert_bytes)
    db.add(LawyerApplication(
        id=ref, status="pending", full_name=name, email=mail, phone=tel, city=town, bar_council=council,
        enrolment_no=enrolment, experience_years=experienceYears, practice_areas=areas, languages=langs,
        office_address=office, about=bio or None, photo_path=photo_path, photo_iv=photo_iv, id_doc_type=idDocType,
        id_file_name=_safe_name(idProof.filename, "id-document"), id_file_path=id_path, id_file_iv=id_iv,
        id_file_hash=HashService.hash_bytes(id_bytes),
        enrolment_file_name=_safe_name(enrolmentCertificate.filename, "enrolment-certificate"),
        enrolment_file_path=cert_path, enrolment_file_iv=cert_iv, enrolment_file_hash=HashService.hash_bytes(cert_bytes),
    ))
    await db.commit()
    LAWYER_APPLICATIONS_PER_IP.hit(ip)
    await _email_quietly(_application_received_email(mail, name, ref))
    notify_admins("lawyer-application", "Lawyer application waiting", [
        f"{name} applied as a lawyer ({council}, enrolment {enrolment}). Review it on the Legal page."], "/admin/legal")
    return {"reference": ref, "email": mail, "status": "pending"}


@router.get("/lawyers/applications/status")  # application status
async def application_status(reference: str, email: str, db: AsyncSession = Depends(get_db)):
    a = await db.get(LawyerApplication, reference.strip().upper())
    if not a or a.email != email.strip().lower():  # both must match: no peeking at other people's applications
        raise HTTPException(status_code=404, detail="We couldn't find an application with that reference and email.")
    return {"reference": a.id, "status": a.status, "submittedAt": iso(a.submitted_at), "reviewedAt": iso(a.reviewed_at),
            "reviewNote": a.review_note if a.status == "rejected" else None}


# ---------- directory (owners) ----------

def require_owner(user: User = Depends(get_current_user)) -> User:
    if account_type(user) != "owner" and not admin_unlocked(user):
        raise field_error("Only home owners can hire a lawyer on TrustRent. Switch to 'Rent out my home' first.",
                          None, status.HTTP_403_FORBIDDEN)
    return user


@router.get("/lawyers")  # lawyer directory
async def directory(request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(LawyerApplication, User).join(User, User.id == LawyerApplication.user_id)
        .where(LawyerApplication.status == "approved", User.is_lawyer.is_(True), User.banned_at.is_(None),
               User.deleted_at.is_(None))
        .order_by(LawyerApplication.experience_years.desc())
    )).all()
    base = str(request.base_url)
    return [lawyer_card(a, u, base) for a, u in rows]


@router.get("/legal/contacts")  # tenants the owner can share with
async def contacts(user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    return await _owner_contacts(db, user)


async def _owner_contacts(db: AsyncSession, owner: User) -> list[dict]:
    via: dict[str, str] = {}
    for seeker_id, title in (await db.execute(
        select(Conversation.seeker_id, Listing.title).join(Listing, Listing.id == Conversation.listing_id)
        .where(Conversation.owner_id == owner.id)
    )).all():
        via.setdefault(seeker_id, f"Chat about {title}")
    for tenant_id, dep_id in (await db.execute(select(Deposit.tenant_id, Deposit.id).where(Deposit.owner_id == owner.id))).all():
        via[tenant_id] = f"Deposit {dep_id}"
    if not via:
        return []
    people = await db.scalars(select(User).where(User.id.in_(via), User.banned_at.is_(None), User.deleted_at.is_(None)))
    return sorted(({"id": u.id, "name": display_name(u), "username": u.username or "", "via": via[u.id]} for u in people),
                  key=lambda x: x["name"].lower())


# ---------- cases: owner <-> lawyer ----------

class CaseIn(BaseModel):
    lawyerId: str
    listingId: str | None = None
    message: str = Field(min_length=1, max_length=2000)


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ShareIn(BaseModel):
    tenantId: str


async def _case_for(db: AsyncSession, case_id: str, user: User, allow_admin: bool = False) -> LegalCase:
    c = await db.get(LegalCase, case_id)
    if not c or not (user.id in (c.owner_id, c.lawyer_id) or (allow_admin and admin_unlocked(user))):
        raise HTTPException(status_code=404, detail="Case not found")
    return c


def _side(c: LegalCase, user: User) -> str:
    return "owner" if user.id == c.owner_id else "lawyer" if user.id == c.lawyer_id else "admin"


def agreement_out(a: Agreement, names: dict[str, str], shares: list[AgreementShare] | None = None) -> dict:
    out = {"id": a.id, "caseId": a.case_id, "title": a.title, "fileName": a.file_name, "fileHash": a.file_hash,
           "size": a.size, "createdAt": iso(a.created_at), "uploadedBy": names.get(a.uploaded_by, "")}
    if shares is not None:
        out["sharedWith"] = [{"id": s.tenant_id, "name": names.get(s.tenant_id, ""), "sharedAt": iso(s.shared_at)} for s in shares]
    return out


async def _names(db: AsyncSession, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    return {u.id: display_name(u) for u in await db.scalars(select(User).where(User.id.in_(ids)))}


async def case_out(db: AsyncSession, c: LegalCase, viewer: User, full: bool = False) -> dict:
    owner, lawyer = await db.get(User, c.owner_id), await db.get(User, c.lawyer_id)
    listing = await db.get(Listing, c.listing_id) if c.listing_id else None
    side = _side(c, viewer)
    mine_read = c.owner_last_read if side == "owner" else c.lawyer_last_read if side == "lawyer" else None
    other = c.lawyer_id if side == "owner" else c.owner_id
    last = await db.scalar(select(LegalMessage).where(LegalMessage.case_id == c.id).order_by(LegalMessage.created_at.desc()).limit(1))
    unread_q = select(func.count()).select_from(LegalMessage).where(LegalMessage.case_id == c.id, LegalMessage.sender_id == other)
    if mine_read:
        unread_q = unread_q.where(LegalMessage.created_at > mine_read)
    out = {
        "id": c.id, "subject": c.subject, "side": side,
        "owner": {"id": c.owner_id, "name": display_name(owner) if owner else "", "phone": owner.phone if owner else "",
                  "email": owner.email if owner else ""},
        "lawyer": {"id": c.lawyer_id, "name": display_name(lawyer) if lawyer else "", "available": _active_lawyer(lawyer)},
        "listing": {"id": listing.id, "title": listing.title, "area": f"{listing.locality}, {listing.city}"} if listing else None,
        "createdAt": iso(c.created_at), "updatedAt": iso(c.updated_at),
        "lastMessage": last.text[:140] if last else "",
        "unread": int(await db.scalar(unread_q) or 0) if side != "admin" else 0,
        "agreements": int(await db.scalar(select(func.count()).select_from(Agreement).where(Agreement.case_id == c.id)) or 0),
    }
    if full:
        msgs = list(await db.scalars(select(LegalMessage).where(LegalMessage.case_id == c.id).order_by(LegalMessage.created_at)))
        docs = list(await db.scalars(select(Agreement).where(Agreement.case_id == c.id).order_by(Agreement.created_at.desc())))
        shares = list(await db.scalars(select(AgreementShare).where(AgreementShare.agreement_id.in_([d.id for d in docs])))) if docs else []
        names = await _names(db, {m.sender_id for m in msgs} | {d.uploaded_by for d in docs} | {s.tenant_id for s in shares})
        out["messages"] = [{"id": m.id, "senderId": m.sender_id, "senderName": names.get(m.sender_id, ""),
                            "from": "owner" if m.sender_id == c.owner_id else "lawyer", "text": m.text,
                            "createdAt": iso(m.created_at)} for m in msgs]
        out["documents"] = [agreement_out(d, names, [s for s in shares if s.agreement_id == d.id]) for d in docs]
    return out


def _application_received_email(to: str, name: str, ref: str):
    from app.services.mailer import _simple_email
    return _simple_email(to, f"We received your lawyer application {ref}", [
        f"Hello {name},", f"Thank you for applying to TrustRent as a lawyer. Your reference is {ref}.",
        "We usually verify lawyers within 24 to 48 hours and will email your sign-in details once you're approved.",
        "TrustRent"])


async def _tell_other_side(db: AsyncSession, c: LegalCase, sender: User, text: str) -> None:
    other_id = c.lawyer_id if sender.id == c.owner_id else c.owner_id
    other_read = c.lawyer_last_read if sender.id == c.owner_id else c.owner_last_read
    if recently_active(other_read):
        return
    notify(await db.get(User, other_id), f"New message from {display_name(sender)}", [
        f"About {c.subject}:", f'"{snippet(text)}"', "Reply on TrustRent."], f"/legal/{c.id}", thread=f"case:{c.id}")


def _add_message(db: AsyncSession, c: LegalCase, sender: User, text: str) -> None:
    now = utcnow()
    db.add(LegalMessage(id=str(uuid.uuid4()), case_id=c.id, sender_id=sender.id, text=text, created_at=now))
    c.updated_at = now
    if sender.id == c.owner_id:
        c.owner_last_read = now
    else:
        c.lawyer_last_read = now


@router.post("/legal/cases", status_code=201)  # hire lawyer
async def open_case(body: CaseIn, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    if is_admin(user):
        raise field_error("Admins can't hire lawyers.", None, status.HTTP_403_FORBIDDEN)
    lawyer = await db.get(User, body.lawyerId)
    if not _active_lawyer(lawyer):
        raise HTTPException(status_code=404, detail=UNAVAILABLE)
    listing = None
    if body.listingId:
        listing = await db.get(Listing, body.listingId)
        if not listing or listing.owner_id != user.id or listing.status == "removed":
            raise field_error("Choose one of your own homes.", "listingId")
    text = body.message.strip()
    if not text:
        raise field_error("Write a message to the lawyer.", "message")
    c = await db.scalar(select(LegalCase).where(LegalCase.owner_id == user.id, LegalCase.lawyer_id == lawyer.id,
                                                LegalCase.listing_id.is_(None) if listing is None else LegalCase.listing_id == listing.id))
    if not c:
        c = LegalCase(id=str(uuid.uuid4()), owner_id=user.id, lawyer_id=lawyer.id, listing_id=listing.id if listing else None,
                      subject=f"Rental agreement: {listing.title}"[:120] if listing else "Rental agreement",
                      created_at=utcnow())
        db.add(c)
        await db.flush()
    other_read = c.lawyer_last_read
    _add_message(db, c, user, text)
    await db.commit()
    if not recently_active(other_read):
        notify(lawyer, f"New agreement request from {display_name(user)}", [
            f"{display_name(user)} wants your help with: {c.subject}.", f'"{snippet(text)}"',
            "Reply in your TrustRent lawyer portal."], f"/legal/{c.id}", thread=f"case:{c.id}")
    return await case_out(db, c, user, full=True)


@router.get("/legal/cases")  # my cases
async def my_cases(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(LegalCase).where(or_(LegalCase.owner_id == user.id, LegalCase.lawyer_id == user.id))
                            .order_by(LegalCase.updated_at.desc()))
    return [await case_out(db, c, user) for c in rows]


@router.get("/legal/cases/{case_id}")  # case
async def get_case(case_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _case_for(db, case_id, user, allow_admin=True)
    return await case_out(db, c, user, full=True)


@router.post("/legal/cases/{case_id}/messages", status_code=201)  # case message
async def case_message(case_id: str, body: TextIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _case_for(db, case_id, user)
    if user.id == c.owner_id and not _active_lawyer(await db.get(User, c.lawyer_id)):
        raise field_error(UNAVAILABLE, None, status.HTTP_409_CONFLICT)
    text = body.text.strip()
    if not text:
        raise field_error("Write a message.", "text")
    _add_message(db, c, user, text)  # only moves the sender's read marker
    await db.commit()
    await _tell_other_side(db, c, user, text)
    return await case_out(db, c, user, full=True)


@router.post("/legal/cases/{case_id}/read")  # mark case read
async def case_read(case_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _case_for(db, case_id, user)
    if user.id == c.owner_id:
        c.owner_last_read = utcnow()
    else:
        c.lawyer_last_read = utcnow()
    await db.commit()
    return {"ok": True}


@router.post("/legal/cases/{case_id}/agreements", status_code=201)  # lawyer uploads agreement
async def upload_agreement(case_id: str, title: str = Form(...), file: UploadFile = File(...),
                           user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _case_for(db, case_id, user)
    if user.id != c.lawyer_id:
        raise HTTPException(status_code=403, detail="Only the lawyer can add the agreement")
    name = _text(title, "title", "a title for the document", 3, 120)
    content = await read_limited(file, MAX_PDF_BYTES, "file", "The PDF is larger than 15 MB.")
    if not content.startswith(b"%PDF-"):
        raise field_error("Upload the agreement as a PDF file.", "file")
    aid = str(uuid.uuid4())
    path, iv = private_storage().store(f"agreement_{aid}", content)
    file_name = _safe_name(file.filename, "agreement.pdf")
    if not file_name.lower().endswith(".pdf"):
        file_name += ".pdf"
    db.add(Agreement(id=aid, case_id=c.id, uploaded_by=user.id, title=name, file_name=file_name, file_path=path,
                     file_iv=iv, file_hash=HashService.hash_bytes(content), size=len(content), created_at=utcnow()))
    _add_message(db, c, user, f"Shared a document: {name}. Download it from the documents list.")
    await db.commit()
    notify(await db.get(User, c.owner_id), f"{display_name(user)} sent you a document", [
        f'Your lawyer shared "{name}" for {c.subject}.', "Download it, read it, and share it with your tenant."], f"/legal/{c.id}")
    return await case_out(db, c, user, full=True)


async def _agreement_access(db: AsyncSession, agreement_id: str, user: User) -> tuple[Agreement, LegalCase]:
    a = await db.get(Agreement, agreement_id)
    c = await db.get(LegalCase, a.case_id) if a else None
    if not a or not c:
        raise HTTPException(status_code=404, detail="Document not found")
    if user.id in (c.owner_id, c.lawyer_id) or admin_unlocked(user):
        return a, c
    shared = await db.scalar(select(AgreementShare.id).where(AgreementShare.agreement_id == a.id, AgreementShare.tenant_id == user.id))
    if not shared:
        raise HTTPException(status_code=404, detail="Document not found")
    return a, c


@router.get("/legal/agreements/{agreement_id}/file")  # download agreement
async def agreement_file(agreement_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    a, _ = await _agreement_access(db, agreement_id, user)
    try:
        content = read_private(a.file_path, a.file_iv)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="This document is no longer stored on the server") from None
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": content_disposition("attachment", a.file_name, "agreement"),
        "Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
    })


@router.post("/legal/agreements/{agreement_id}/share")  # owner shares with tenant
async def share_agreement(agreement_id: str, body: ShareIn, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    a, c = await _agreement_access(db, agreement_id, user)
    if user.id != c.owner_id:
        raise HTTPException(status_code=403, detail="Only the owner can share the agreement")
    known = {p["id"] for p in await _owner_contacts(db, user)}
    if body.tenantId not in known:  # only people the owner already deals with on TrustRent
        raise field_error("Choose a tenant who has messaged you about a home or paid you a deposit.", "tenantId")
    if not await db.scalar(select(AgreementShare.id).where(AgreementShare.agreement_id == a.id,
                                                           AgreementShare.tenant_id == body.tenantId)):
        db.add(AgreementShare(id=str(uuid.uuid4()), agreement_id=a.id, tenant_id=body.tenantId, shared_by=user.id,
                              shared_at=utcnow()))
        await db.commit()
        notify(await db.get(User, body.tenantId), f"{display_name(user)} shared a rental agreement with you", [
            f'"{a.title}" was prepared by a TrustRent-verified lawyer.', "Download it and read it before you sign."], "/agreements")
    return await case_out(db, c, user, full=True)


@router.get("/legal/agreements")  # agreements shared with me
async def shared_with_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(AgreementShare, Agreement, LegalCase).join(Agreement, Agreement.id == AgreementShare.agreement_id)
        .join(LegalCase, LegalCase.id == Agreement.case_id).where(AgreementShare.tenant_id == user.id)
        .order_by(AgreementShare.shared_at.desc())
    )).all()
    names = await _names(db, {c.owner_id for _, _, c in rows} | {c.lawyer_id for _, _, c in rows} | {a.uploaded_by for _, a, _ in rows})
    out = []
    for s, a, c in rows:
        listing = await db.get(Listing, c.listing_id) if c.listing_id else None
        out.append(agreement_out(a, names) | {
            "sharedAt": iso(s.shared_at), "owner": names.get(c.owner_id, ""), "lawyer": names.get(c.lawyer_id, ""),
            "listing": listing.title if listing else None,
        })
    return out


# ---------- admin ----------

class ReviewIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


@router.get("/admin/legal")  # admin legal desk
async def admin_legal(request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    base = str(request.base_url)
    apps = list(await db.scalars(select(LawyerApplication).order_by(LawyerApplication.submitted_at.desc())))
    users = {u.id: u for u in await db.scalars(select(User).where(User.is_lawyer.is_(True)))}
    cases = list(await db.scalars(select(LegalCase).order_by(LegalCase.updated_at.desc())))
    case_count: dict[str, int] = {}
    for c in cases:
        case_count[c.lawyer_id] = case_count.get(c.lawyer_id, 0) + 1
    doc_counts = dict((await db.execute(select(Agreement.case_id, func.count()).group_by(Agreement.case_id))).all())
    msg_counts = dict((await db.execute(select(LegalMessage.case_id, func.count()).group_by(LegalMessage.case_id))).all())
    names = await _names(db, {c.owner_id for c in cases} | {c.lawyer_id for c in cases})
    lawyers = []
    for a in apps:
        u = users.get(a.user_id or "")
        if a.status == "approved" and u and not u.deleted_at:
            lawyers.append(lawyer_card(a, u, base) | {
                "username": u.username, "reference": a.id, "approvedAt": iso(a.reviewed_at),
                "banned": {"at": iso(u.banned_at), "reason": u.ban_reason} if u.banned_at else None,
                "passwordSet": not u.must_change_password,
                "cases": case_count.get(u.id, 0),
                "agreements": sum(doc_counts.get(c.id, 0) for c in cases if c.lawyer_id == u.id),
            })
    return {
        "applications": [application_out(a, base) for a in apps],
        "lawyers": lawyers,
        "cases": [{"id": c.id, "subject": c.subject, "owner": {"id": c.owner_id, "name": names.get(c.owner_id, "")},
                   "lawyer": {"id": c.lawyer_id, "name": names.get(c.lawyer_id, "")}, "messages": msg_counts.get(c.id, 0),
                   "agreements": doc_counts.get(c.id, 0), "updatedAt": iso(c.updated_at)} for c in cases],
    }


@router.get("/admin/legal/applications/{reference}/{doc}")  # application document
async def application_document(reference: str, doc: str, admin: User = Depends(require_full_admin),
                               db: AsyncSession = Depends(get_db)):
    a = await db.get(LawyerApplication, reference)
    files = {"photo": ("photo_path", "photo_iv", "photo.jpg"), "id": ("id_file_path", "id_file_iv", "id_file_name"),
             "enrolment": ("enrolment_file_path", "enrolment_file_iv", "enrolment_file_name")}
    if not a or doc not in files:
        raise HTTPException(status_code=404, detail="Not found")
    path_attr, iv_attr, name = files[doc]
    if not getattr(a, path_attr):
        raise HTTPException(status_code=410, detail="This document was deleted")
    try:
        content = read_private(getattr(a, path_attr), getattr(a, iv_attr))
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="This document is no longer stored on the server") from None
    return _file_response(content, name if doc == "photo" else getattr(a, name))


def _credentials(username: str, password: str, emailed: bool) -> dict:
    return {"username": username, "password": password, "emailed": emailed}


@router.post("/admin/legal/applications/{reference}/review")  # approve lawyer
async def review_application(reference: str, body: ReviewIn, admin: User = Depends(require_full_admin),
                             db: AsyncSession = Depends(get_db)):
    a = await db.get(LawyerApplication, reference)
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    if a.status != "pending":
        raise field_error("This application was already decided.", None, status.HTTP_409_CONFLICT)
    a.reviewed_at, a.reviewed_by = utcnow(), admin.id
    if not body.approve:
        a.status = "rejected"
        a.review_note = (body.note or "").strip() or "We couldn't verify your enrolment details. Check them and apply again."
        await db.commit()
        await _email_quietly(build_lawyer_rejected_email(a.email, a.full_name, a.id, a.review_note))
        return {"application": application_out(a)}
    taken = await _identity_taken(db, a.email, a.phone, skip_application=a.id)
    if taken:
        await db.rollback()
        raise field_error(f"Can't create the account: {taken[1]}", taken[0], status.HTTP_409_CONFLICT)
    first, _, last = a.full_name.partition(" ")
    username, password = await _new_username(db, a.full_name), _temp_password()
    user = User(id=str(uuid.uuid4()), email=a.email, name=a.full_name, first_name=first, last_name=last.strip() or first,
                username=username, phone=a.phone, country="India", provider="password", password_hash=hash_secret(password),
                role=UserRole.TENANT, is_verified=True, is_lawyer=True, must_change_password=True)
    db.add(user)
    try:
        a.public_photo = save_public(f"lawyers/{user.id}.jpg", read_private(a.photo_path, a.photo_iv), "image/jpeg")
    except FileNotFoundError:
        a.public_photo = None
    a.status, a.user_id, a.review_note = "approved", user.id, None
    await db.commit()
    emailed = await _email_quietly(build_lawyer_approved_email(a.email, a.full_name, username, password))
    return {"application": application_out(a), "credentials": _credentials(username, password, emailed)}


@router.post("/admin/legal/lawyers/{user_id}/reset-password")  # new lawyer password
async def reset_lawyer_password(user_id: str, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    u = await db.get(User, user_id)
    if not u or not u.is_lawyer or u.deleted_at:
        raise HTTPException(status_code=404, detail="Lawyer not found")
    password = _temp_password()
    u.password_hash, u.must_change_password, u.password_changed_at = hash_secret(password), True, utcnow()
    await db.commit()
    emailed = await _email_quietly(build_lawyer_approved_email(u.email, display_name(u), u.username or "", password))
    return {"credentials": _credentials(u.username or "", password, emailed)}
