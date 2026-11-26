from sqlalchemy import func, select
from app.core.database import AsyncSessionLocal
from app.models.deposits import Deposit, LedgerEntry
from app.models.marketplace import Listing
from app.models.user import User
from app.services.ledger import ledger_state
from app.services.seed import remove_sample_data, seed_demo_deposits, seed_sample_listings
from tests.test_marketplace import owner_with_listing, signup
async def test_remove_sample_data_keeps_real_users(client):
    async with AsyncSessionLocal() as db:
        await seed_sample_listings(db)
    async with AsyncSessionLocal() as db:
        await seed_demo_deposits(db)
    owner, oh, listing = await owner_with_listing(client)
    seeker, sh = await signup(client)
    sample = (await client.get("/api/v1/listings", headers=sh, params={"city": "Indore"})).json()
    codes = [(await client.post("/api/v1/conversations", headers=sh, json={"listingId": x["id"]})).status_code for x in sample]
    assert any(c in (200, 201) for c in codes)
    async with AsyncSessionLocal() as db:
        blocks = await db.scalar(select(func.count()).select_from(LedgerEntry))
        assert await remove_sample_data(db) > 0
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(User).where(User.is_demo.is_(True))) == 0
        assert await db.scalar(select(func.count()).select_from(Listing).where(Listing.listed_days_ago.is_not(None))) == 0
        assert await db.scalar(select(func.count()).select_from(Deposit).where(Deposit.id.like("DEP-DEMO%"))) == 0
        assert await db.get(Listing, listing["id"]) is not None
        assert await db.scalar(select(func.count()).select_from(LedgerEntry)) == blocks
        assert (await ledger_state(db))[1] is True
        assert await remove_sample_data(db) == 0
    assert (await client.get("/api/v1/users/me", headers=sh)).status_code == 200
    assert (await client.get("/api/v1/inbox", headers=sh)).json()["conversations"] == []
    async with AsyncSessionLocal() as db:
        await seed_sample_listings(db)