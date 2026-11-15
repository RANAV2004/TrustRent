import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.errors import field_error
from app.core.ratelimit import enforce
from app.models.marketplace import IdentitySubmission, utcnow
from app.models.trust import DigilockerSession
from app.models.user import User
from app.services import digilocker
from app.services.accounts import user_out
from app.services.audit import audit
from app.services.hash_service import HashService
from app.services.register import try_rebuild_register

router = APIRouter(prefix="/identity/digilocker", tags=["DigiLocker"])


class CompleteIn(BaseModel):
    code: str = Field(min_length=4, max_length=512)
    state: str = Field(min_length=8, max_length=64)


@router.get("/start")  # where to send the user
async def start(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not digilocker.enabled():
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="DigiLocker isn't set up on this server")
    enforce(f"digilocker:user:{user.id}", 10, 3600, "Too many DigiLocker attempts. Try again later.")
    state, verifier, challenge = digilocker.new_pkce()
    db.add(DigilockerSession(state=state, user_id=user.id, verifier=verifier, expires_at=utcnow() + digilocker.SESSION_TTL))
    await db.commit()
    return {"url": digilocker.authorize_url(state, challenge)}


@router.post("/complete")  # back from DigiLocker with ?code&state
async def complete(body: CompleteIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    s = await db.get(DigilockerSession, body.state)
    if not s or s.used or s.user_id != user.id or s.expires_at < utcnow():
        raise field_error("This DigiLocker sign-in expired. Start again.", None, status.HTTP_400_BAD_REQUEST)
    s.used = True
    await db.commit()
    try:
        info = digilocker.parse_eaadhaar(await digilocker.fetch_eaadhaar(body.code, s.verifier))
    except digilocker.DigilockerError as e:
        raise field_error(str(e), None, status.HTTP_502_BAD_GATEWAY) from None
    ok = digilocker.names_match(user.first_name or user.name, user.last_name or "", info["name"])
    masked = f"Aadhaar ending {info['last4']}" if info["last4"] else "Aadhaar"
    note = f"{masked} via DigiLocker; name matches" if ok else (
        f"{masked} via DigiLocker; the name on Aadhaar ({info['name']}) differs from the account name, so an admin will check it")
    db.add(IdentitySubmission(id=str(uuid.uuid4()), user_id=user.id, doc_type="DigiLocker e-Aadhaar", file_name="digilocker",
                              file_path="", file_iv="", file_hash=HashService.hash_text(f"{user.id}:{info['last4']}:{info['dob']}"),
                              status="approved" if ok else "pending", reviewed_at=utcnow() if ok else None,
                              reviewed_by="DigiLocker" if ok else None, review_note=note))
    if ok:
        user.is_verified = True
    audit(db, user, "identity.digilocker", "user", user.id, matched=ok, last4=info["last4"])
    await db.commit()
    await db.refresh(user)
    await try_rebuild_register(db)
    return {"user": user_out(user), "matched": ok, "pendingReview": not ok,
            "message": "Verified with DigiLocker." if ok else "Your Aadhaar name is different from your account name. An admin will check it."}
