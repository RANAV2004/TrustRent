import html
import re
import uuid
from datetime import date
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
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
from app.services.audit import audit
from app.services.files import private_storage, read_private
from app.services.images import is_document, read_limited
from app.services.notify import notify
from app.services import esign
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


def render_text(t: dict, d: Deposit, listing: Listing | None, tenant: User, owner: User, a: Agreement | None = None) -> str:
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
    if a is not None and a.estamp_number:
        lines.append(f"E-stamp: certificate {a.estamp_number}, {a.estamp_state}, stamp duty Rs {a.estamp_amount:,}. "
                     "The e-stamp certificate is attached to this agreement on TrustRent.")
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
            "estamp": {"state": a.estamp_state, "number": a.estamp_number, "amount": a.estamp_amount,
                       "fileHash": a.estamp_file_hash} if a.estamp_number else None,
            "esign": {"status": a.esign_status, "signedAt": iso(a.esigned_at), "pdfHash": a.esigned_hash,
                      "links": (a.esign_links or {}).get(me) if me else None} if a.esign_status else None,
        },
        "esignAvailable": esign.enabled() and not sigs and a.esign_status in (None, "failed"),
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
    if a:
        await _unsigned(db, a)
    terms = body.model_dump()
    terms["maintenance"] = re.sub(r"\s+", " ", terms["maintenance"]).strip()
    terms["extraClauses"] = terms["extraClauses"].strip()
    if not a:
        a = Agreement(id=str(uuid.uuid4()), deposit_id=d.id, created_by=user.id)
        db.add(a)
    text = render_text(terms, d, listing, tenant, owner, a)
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
    if a.esign_status == "requested":
        raise field_error("Aadhaar eSign has started for this agreement. Use the link our eSign partner emailed you.", None,
                          status.HTTP_409_CONFLICT)
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
    roles = set(await db.scalars(select(AgreementSignature.role).where(AgreementSignature.agreement_id == a.id)))
    if roles >= {"tenant", "owner"}:  # fully signed: monthly rent starts
        from app.services.rent import create_schedule
        await create_schedule(db, a, d)
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



ESTAMP_STATES = {"Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
                 "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab", "Rajasthan",
                 "Tamil Nadu", "Telangana", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Chandigarh", "Puducherry",
                 "Jammu and Kashmir", "Other"}


async def _agreement_for(db: AsyncSession, d: Deposit) -> Agreement:
    a = await db.scalar(select(Agreement).where(Agreement.deposit_id == d.id))
    if not a:
        raise HTTPException(status_code=404, detail="No agreement yet")
    return a


async def _unsigned(db: AsyncSession, a: Agreement) -> None:
    if await db.scalar(select(AgreementSignature.id).where(AgreementSignature.agreement_id == a.id).limit(1)) or a.esign_status == "requested":
        raise field_error("Someone already started signing, so the agreement can't be changed.", None, status.HTTP_409_CONFLICT)


@router.post("/deposits/{deposit_id}/agreement/estamp")  # attach e-stamp paper bought by the owner
async def attach_estamp(deposit_id: str, state: str = Form(...), certificateNumber: str = Form(..., max_length=40),
                        amount: int = Form(..., ge=1, le=10_000_000), file: UploadFile = File(...),
                        user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, listing, tenant, owner = await _context(db, deposit_id, user)
    if user.id != d.owner_id:
        raise HTTPException(status_code=403, detail="Only the owner attaches the e-stamp")
    a = await _agreement_for(db, d)
    await _unsigned(db, a)
    if state not in ESTAMP_STATES:
        raise field_error("Choose the state the e-stamp was bought in.", "state")
    number = certificateNumber.strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{6,40}", number):
        raise field_error("Enter the e-stamp certificate number exactly as printed (letters and digits).", "certificateNumber")
    raw = await read_limited(file, 10 * 1024 * 1024, "file")
    if not raw or not is_document(raw):
        raise field_error("Upload the e-stamp certificate as a PDF or photo.", "file")
    path, iv = private_storage().store(f"estamp_{a.id}", raw)
    a.estamp_state, a.estamp_number, a.estamp_amount = state, number, amount
    a.estamp_file_path, a.estamp_file_iv, a.estamp_file_hash = path, iv, HashService.hash_bytes(raw)
    a.text = render_text(a.terms, d, listing, tenant, owner, a)  # the e-stamp is part of what gets signed
    a.text_hash = HashService.hash_text(a.text)
    await db.flush()
    a.record_tx = (await record_event(db, d.id, "agreement", {"agreementId": a.id, "textHash": a.text_hash,
                                                              "estampHash": a.estamp_file_hash})).entry_hash
    await db.commit()
    return await _out(db, a, d, user)


@router.get("/deposits/{deposit_id}/agreement/estamp")
async def estamp_file(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, *_ = await _context(db, deposit_id, user)
    a = await _agreement_for(db, d)
    if not a.estamp_file_path:
        raise HTTPException(status_code=404, detail="No e-stamp attached")
    raw = read_private(a.estamp_file_path, a.estamp_file_iv)
    media = "application/pdf" if raw.startswith(b"%PDF") else "image/jpeg" if raw[:3] == b"\xff\xd8\xff" else "application/octet-stream"
    return Response(raw, media_type=media, headers={"Content-Disposition": f'inline; filename="estamp-{d.id}"',
                                                     "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.post("/deposits/{deposit_id}/agreement/esign")  # start Aadhaar eSign for both sides
async def start_esign(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, listing, tenant, owner = await _context(db, deposit_id, user)
    if user.id not in (d.tenant_id, d.owner_id):
        raise HTTPException(status_code=403, detail="Only the tenant and the owner can start signing")
    if not esign.enabled():
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Aadhaar eSign isn't set up on this server")
    a = await _agreement_for(db, d)
    await _unsigned(db, a)
    pdf = esign.agreement_pdf(a.text, f"TrustRent deposit {d.id}. Text fingerprint (SHA-256): {a.text_hash}")
    signers = [{"identifier": owner.email, "name": display_name(owner)}, {"identifier": tenant.email, "name": display_name(tenant)}]
    try:
        doc_id = await esign.create_request(pdf, f"rent-agreement-{d.id}.pdf", signers)
    except esign.EsignError as e:
        raise field_error(str(e), None, status.HTTP_502_BAD_GATEWAY) from None
    a.esign_provider, a.esign_doc_id, a.esign_status = settings.ESIGN_PROVIDER, doc_id, "requested"
    a.esign_links = {"owner": esign.sign_link(doc_id, owner.email), "tenant": esign.sign_link(doc_id, tenant.email)}
    audit(db, user, "agreement.esign_requested", "deposit", d.id, document=doc_id)
    await db.commit()
    for u in (tenant, owner):
        notify(u, f"Sign your rent agreement with Aadhaar ({d.id})",
               ["Our eSign partner has emailed you a link. Signing uses an OTP sent to your Aadhaar-linked mobile."], "/deposits")
    return await _out(db, a, d, user)


async def refresh_esign(db: AsyncSession, a: Agreement) -> bool:
    """Ask the provider directly; never trust a webhook body. Returns True when it just completed."""
    if a.esign_status != "requested" or not a.esign_doc_id:
        return False
    doc = await esign.fetch(a.esign_doc_id)
    if not esign.is_complete(doc):
        return False
    pdf = await esign.download(a.esign_doc_id)
    d = await db.get(Deposit, a.deposit_id)
    path, iv = private_storage().store(f"esigned_{a.id}", pdf)
    a.esigned_pdf_path, a.esigned_pdf_iv, a.esigned_hash = path, iv, HashService.hash_bytes(pdf)
    a.esign_status, a.esigned_at = "completed", utcnow()
    have = set(await db.scalars(select(AgreementSignature.role).where(AgreementSignature.agreement_id == a.id)))
    for role, uid in (("owner", d.owner_id), ("tenant", d.tenant_id)):
        if role not in have:
            db.add(AgreementSignature(id=str(uuid.uuid4()), agreement_id=a.id, user_id=uid, role=role, typed_name="Aadhaar eSign",
                                      text_hash=a.text_hash, signed_at=a.esigned_at))
    await db.flush()
    await record_event(db, d.id, "esign", {"agreementId": a.id, "pdfHash": a.esigned_hash, "textHash": a.text_hash})
    from app.services.rent import create_schedule
    await create_schedule(db, a, d)
    await db.commit()
    for uid in (d.tenant_id, d.owner_id):
        notify(await db.get(User, uid), f"Rent agreement signed with Aadhaar ({d.id})", ["Both sides signed. The signed PDF is on TrustRent."], "/deposits")
    return True


@router.post("/deposits/{deposit_id}/agreement/esign/refresh")  # check signing progress
async def esign_refresh(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, *_ = await _context(db, deposit_id, user)
    a = await _agreement_for(db, d)
    try:
        await refresh_esign(db, a)
    except esign.EsignError as e:
        raise field_error(str(e), None, status.HTTP_502_BAD_GATEWAY) from None
    return await _out(db, a, d, user)


@router.post("/agreements/esign/webhook", include_in_schema=False)  # provider ping: we re-check with the provider
async def esign_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        body = await request.json()
    except ValueError:
        return {"ok": False}
    ids = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("id", "document_id") and isinstance(v, str):
                    ids.add(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(body)
    done = 0
    for doc_id in list(ids)[:5]:
        a = await db.scalar(select(Agreement).where(Agreement.esign_doc_id == doc_id))
        if a:
            try:
                done += await refresh_esign(db, a)
            except esign.EsignError:
                pass
    return {"ok": True, "completed": done}


@router.get("/deposits/{deposit_id}/agreement/esigned.pdf")  # the Aadhaar-signed PDF
async def esigned_pdf(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d, *_ = await _context(db, deposit_id, user)
    a = await _agreement_for(db, d)
    if not a.esigned_pdf_path:
        raise HTTPException(status_code=404, detail="Not signed with Aadhaar yet")
    return Response(read_private(a.esigned_pdf_path, a.esigned_pdf_iv), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="rent-agreement-{d.id}-signed.pdf"', "Cache-Control": "no-store"})
