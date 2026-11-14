import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.errors import field_error
from app.models.extras import SavedSearch
from app.models.marketplace import utcnow
from app.models.user import User
from app.services.accounts import iso
from app.services.search import Filters

router = APIRouter(tags=["Saved searches"])
MAX_SAVED = 10


class SavedIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    filters: dict


def out(s: SavedSearch) -> dict:
    return {"id": s.id, "name": s.name, "filters": s.filters, "createdAt": iso(s.created_at), "lastAlertAt": iso(s.last_alert_at)}


@router.get("/searches")  # my saved searches
async def list_saved(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [out(s) for s in await db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.created_at.desc()))]


@router.post("/searches", status_code=201)  # save search + email alerts
async def save(body: SavedIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    f = Filters.from_dict(body.filters)
    if not f.q.strip():
        raise field_error("Search for a city, area or pin code first.", "filters")
    count = await db.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user.id))
    if (count or 0) >= MAX_SAVED:
        raise field_error(f"You can save up to {MAX_SAVED} searches. Delete one first.", None, status.HTTP_409_CONFLICT)
    s = SavedSearch(id=str(uuid.uuid4()), user_id=user.id, name=body.name.strip(), filters=f.as_dict(), created_at=utcnow())
    db.add(s)
    await db.commit()
    return out(s)


@router.delete("/searches/{sid}", status_code=204)
async def delete(sid: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    s = await db.get(SavedSearch, sid)
    if not s or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await db.delete(s)
    await db.commit()
