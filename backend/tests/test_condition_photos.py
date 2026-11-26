import io
from PIL import Image
from sqlalchemy import update
from app.core.database import AsyncSessionLocal
from app.models.deposits import ConditionPhoto
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing, signup
def jpeg_with_gps() -> bytes:  # test photo
    img = Image.new("RGB", (64, 48), (200, 120, 40))
    exif = Image.Exif()
    exif[0x8825] = {2: (22, 43, 0), 4: (75, 53, 0)}
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()
async def paid_deposit(client):
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    order = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
    dep_id = (await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order.json()["orderId"]})).json()["depositId"]
    return dep_id, th, oh
def upload(client, dep_id, headers, stage="move_in", room="Bedroom 1", data=None):
    return client.post(f"/api/v1/deposits/{dep_id}/photos", headers=headers, data={"stage": stage, "room": room, "note": "Wall near window"},
                       files={"file": ("room.jpg", io.BytesIO(data or jpeg_with_gps()), "image/jpeg")})
async def test_photos_move_in_move_out_and_receipts(client):
    dep_id, th, oh = await paid_deposit(client)
    res = await upload(client, dep_id, th)
    assert res.status_code == 201, res.text
    p = res.json()
    assert p["side"] == "tenant" and p["stage"] == "move_in" and p["verified"] is True and p["receipt"].startswith("0x")
    assert (await upload(client, dep_id, oh, room="Kitchen")).json()["side"] == "owner"
    assert (await client.get(f"/api/v1/deposits/{dep_id}/photos/{p['id']}/file", headers=oh)).status_code == 404
    mine = (await client.get(f"/api/v1/deposits/{dep_id}/photos", headers=oh)).json()
    assert mine["compare"] is False and [x["side"] for x in mine["photos"]] == ["owner"]
    img = await client.get(f"/api/v1/deposits/{dep_id}/photos/{p['id']}/file", headers=th)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert 0x8825 not in Image.open(io.BytesIO(img.content)).getexif()
    stranger, sh = await signup(client)
    assert (await client.get(f"/api/v1/deposits/{dep_id}/photos", headers=sh)).status_code == 404
    assert (await upload(client, dep_id, sh)).status_code == 404
    assert (await upload(client, dep_id, th, room="Garage")).status_code == 400
    assert (await upload(client, dep_id, th, data=b"not a photo")).status_code == 400
    await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 1500, "reason": "Crack in the bedroom wall near the window"})
    assert (await upload(client, dep_id, th)).status_code == 409
    assert (await upload(client, dep_id, oh, stage="move_out")).status_code == 201
    ah = await admin_headers(client)
    listing = (await client.get(f"/api/v1/deposits/{dep_id}/photos", headers=ah)).json()
    assert listing["side"] is None and listing["compare"] is True and listing["canUpload"] == {"move_in": False, "move_out": False}
    assert [x["stage"] for x in listing["photos"]] == ["move_in", "move_in", "move_out"]
    assert all(x["verified"] for x in listing["photos"])
    ledger = (await client.get("/api/v1/admin/ledger", headers=ah)).json()
    assert ledger["intact"] is True and sum(b["kind"] == "photo" and b["depositId"] == dep_id for b in ledger["blocks"]) == 3
    dep = (await client.get(f"/api/v1/deposits/{dep_id}", headers=th)).json()
    assert dep["verification"]["verified"] is True
    async with AsyncSessionLocal() as db:
        await db.execute(update(ConditionPhoto).where(ConditionPhoto.id == p["id"]).values(room="Kitchen"))
        await db.commit()
    again = (await client.get(f"/api/v1/deposits/{dep_id}/photos", headers=ah)).json()
    assert next(x for x in again["photos"] if x["id"] == p["id"])["verified"] is False
    await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": True})
    assert (await upload(client, dep_id, th, stage="move_out")).status_code == 409