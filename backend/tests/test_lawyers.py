import io
import uuid
from PIL import Image
from tests.mailbox import OUTBOX  # noqa: F401  (keeps the outbox fixture's mailer patched)
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing, signup

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 40), (20, 120, 90)).save(out, format="JPEG")
    return out.getvalue()


def application(tag: str, **over) -> tuple[dict, dict]:
    data = {
        "fullName": "Meera Kulkarni", "email": f"meera_{tag}@lawfirm.in", "phone": f"+9198{int(tag, 16) % 10**8:08d}",
        "city": "Indore", "barCouncil": "Bar Council of Madhya Pradesh", "enrolmentNo": f"MP/{int(tag, 16) % 9999}/2014",
        "experienceYears": "11", "practiceAreas": ["Rental and lease agreements", "Property registration"],
        "languages": "Hindi, English", "officeAddress": "12 MG Road, Indore 452001", "about": "Rent agreements in a day.",
        "idDocType": "PAN card",
    } | over
    files = {"photo": ("me.jpg", io.BytesIO(jpeg()), "image/jpeg"),
             "idProof": ("pan.jpg", io.BytesIO(b"\xff\xd8\xffpan"), "image/jpeg"),
             "enrolmentCertificate": ("bar.pdf", io.BytesIO(b"%PDF-cert"), "application/pdf")}
    return data, files


async def apply(client, tag=None, **over):
    tag = tag or uuid.uuid4().hex[:6]
    data, files = application(tag, **over)
    return await client.post("/api/v1/lawyers/applications", data=data, files=files), data


async def approved_lawyer(client, ah):
    res, data = await apply(client)
    assert res.status_code == 201, res.text
    ref = res.json()["reference"]
    ok = await client.post(f"/api/v1/admin/legal/applications/{ref}/review", headers=ah, json={"approve": True})
    assert ok.status_code == 200, ok.text
    creds = ok.json()["credentials"]
    login = await client.post("/api/v1/auth/password-login", json={"identifier": creds["username"], "password": creds["password"]})
    assert login.status_code == 200, login.text
    return login.json()["user"], {"Authorization": f"Bearer {login.json()['access_token']}"}, creds, data


async def test_application_validation_and_status(client):
    bad, _ = await apply(client, enrolmentNo="??")
    assert bad.status_code == 400 and bad.json()["detail"]["field"] == "enrolmentNo"
    bad, _ = await apply(client, practiceAreas=["Astrology"])
    assert bad.json()["detail"]["field"] == "practiceAreas"
    data, files = application(uuid.uuid4().hex[:6])
    files["photo"] = ("me.jpg", io.BytesIO(b"<html>"), "image/jpeg")
    bad = await client.post("/api/v1/lawyers/applications", data=data, files=files)
    assert bad.json()["detail"]["field"] == "photo"
    tag = uuid.uuid4().hex[:6]
    res, data = await apply(client, tag)
    assert res.status_code == 201 and res.json()["reference"].startswith("LAW-")
    again, _ = await apply(client, tag)
    assert again.status_code == 409  # same email still waiting
    ref = res.json()["reference"]
    assert (await client.get("/api/v1/lawyers/applications/status", params={"reference": ref, "email": "x@y.com"})).status_code == 404
    st = await client.get("/api/v1/lawyers/applications/status", params={"reference": ref.lower(), "email": data["email"].upper()})
    assert st.json()["status"] == "pending"
    user, _ = await signup(client)
    taken, _ = await apply(client, email=user["email"])
    assert taken.status_code == 409 and taken.json()["detail"]["field"] == "email"


async def test_rejection_tells_the_applicant(client):
    ah = await admin_headers(client)
    res, data = await apply(client)
    ref = res.json()["reference"]
    user, uh = await signup(client)
    assert (await client.post(f"/api/v1/admin/legal/applications/{ref}/review", headers=uh, json={"approve": True})).status_code == 403
    doc = await client.get(f"/api/v1/admin/legal/applications/{ref}/enrolment", headers=ah)
    assert doc.status_code == 200 and doc.content == b"%PDF-cert"
    no = await client.post(f"/api/v1/admin/legal/applications/{ref}/review", headers=ah, json={"approve": False, "note": "Enrolment number not found"})
    assert no.json()["application"]["status"] == "rejected"
    st = (await client.get("/api/v1/lawyers/applications/status", params={"reference": ref, "email": data["email"]})).json()
    assert st["status"] == "rejected" and st["reviewNote"] == "Enrolment number not found"
    twice = await client.post(f"/api/v1/admin/legal/applications/{ref}/review", headers=ah, json={"approve": True})
    assert twice.status_code == 409
    retry, _ = await apply(client, email=data["email"], phone=data["phone"], enrolmentNo=data["enrolmentNo"])
    assert retry.status_code == 201  # can apply again after a rejection


async def test_lawyer_hiring_agreement_and_sharing(client):
    ah = await admin_headers(client)
    lawyer, lh, creds, data = await approved_lawyer(client, ah)
    assert lawyer["accountType"] == "lawyer" and lawyer["mustChangePassword"] is True
    assert creds["username"].startswith("adv_meera")
    # first sign-in: choose a password, other sessions end
    wrong = await client.put("/api/v1/users/me/password", headers=lh, json={"currentPassword": "nope", "newPassword": "Lawyer2026"})
    assert wrong.status_code == 400 and wrong.json()["detail"]["field"] == "currentPassword"
    changed = await client.put("/api/v1/users/me/password", headers=lh, json={"currentPassword": creds["password"], "newPassword": "Lawyer2026"})
    assert changed.status_code == 200 and changed.json()["user"]["mustChangePassword"] is False
    assert (await client.get("/api/v1/users/me", headers=lh)).status_code == 401
    lh = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    # lawyers stay lawyers
    assert (await client.put("/api/v1/users/me/account-type", headers=lh, json={"accountType": "owner"})).status_code == 403
    # owners see the directory; seekers don't
    owner, oh, listing = await owner_with_listing(client)
    seeker, sh = await signup(client)
    assert (await client.get("/api/v1/lawyers", headers=sh)).status_code == 403
    cards = (await client.get("/api/v1/lawyers", headers=oh)).json()
    card = next(c for c in cards if c["id"] == lawyer["id"])
    assert card["enrolmentNo"] == data["enrolmentNo"] and card["photo"].endswith(f"/media/lawyers/{lawyer['id']}.jpg")
    assert card["practiceAreas"] == ["Rental and lease agreements", "Property registration"] and card["languages"] == ["Hindi", "English"]
    # the lawyer can't contact owners about homes
    assert (await client.post("/api/v1/conversations", headers=lh, json={"listingId": listing["id"]})).status_code in (403, 404)
    # owner hires the lawyer for a home
    case = await client.post("/api/v1/legal/cases", headers=oh, json={"lawyerId": lawyer["id"], "listingId": listing["id"],
                                                                      "message": "Please draft an 11-month agreement."})
    assert case.status_code == 201, case.text
    cid = case.json()["id"]
    assert case.json()["subject"].startswith("Rental agreement: ")
    same = await client.post("/api/v1/legal/cases", headers=oh, json={"lawyerId": lawyer["id"], "listingId": listing["id"], "message": "Any update?"})
    assert same.json()["id"] == cid and len(same.json()["messages"]) == 2
    inbox = (await client.get("/api/v1/legal/cases", headers=lh)).json()
    assert inbox[0]["id"] == cid and inbox[0]["unread"] == 2 and inbox[0]["side"] == "lawyer"
    await client.post(f"/api/v1/legal/cases/{cid}/read", headers=lh)
    assert (await client.get("/api/v1/legal/cases", headers=lh)).json()[0]["unread"] == 0
    reply = await client.post(f"/api/v1/legal/cases/{cid}/messages", headers=lh, json={"text": "Send me the tenant's details."})
    assert reply.status_code == 201
    stranger, xh = await signup(client)
    assert (await client.get(f"/api/v1/legal/cases/{cid}", headers=xh)).status_code == 404
    # only the lawyer uploads, only PDFs
    assert (await client.post(f"/api/v1/legal/cases/{cid}/agreements", headers=oh, data={"title": "Draft"},
                              files={"file": ("a.pdf", io.BytesIO(PDF), "application/pdf")})).status_code == 403
    notpdf = await client.post(f"/api/v1/legal/cases/{cid}/agreements", headers=lh, data={"title": "Draft"},
                               files={"file": ("a.pdf", io.BytesIO(b"hello"), "application/pdf")})
    assert notpdf.status_code == 400
    up = await client.post(f"/api/v1/legal/cases/{cid}/agreements", headers=lh, data={"title": "Leave and licence agreement"},
                           files={"file": ("agreement.pdf", io.BytesIO(PDF), "application/pdf")})
    assert up.status_code == 201
    doc = up.json()["documents"][0]
    assert doc["title"] == "Leave and licence agreement" and doc["fileHash"].startswith("0x")
    got = await client.get(f"/api/v1/legal/agreements/{doc['id']}/file", headers=oh)
    assert got.content == PDF and got.headers["content-type"] == "application/pdf" and "attachment" in got.headers["content-disposition"]
    assert (await client.get(f"/api/v1/legal/agreements/{doc['id']}/file", headers=xh)).status_code == 404
    # sharing only with tenants the owner knows
    nope = await client.post(f"/api/v1/legal/agreements/{doc['id']}/share", headers=oh, json={"tenantId": stranger["id"]})
    assert nope.status_code == 400
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    people = (await client.get("/api/v1/legal/contacts", headers=oh)).json()
    assert any(p["id"] == tenant["id"] for p in people)
    assert (await client.post(f"/api/v1/legal/agreements/{doc['id']}/share", headers=lh, json={"tenantId": tenant["id"]})).status_code == 403
    shared = await client.post(f"/api/v1/legal/agreements/{doc['id']}/share", headers=oh, json={"tenantId": tenant["id"]})
    assert shared.json()["documents"][0]["sharedWith"][0]["id"] == tenant["id"]
    mine = (await client.get("/api/v1/legal/agreements", headers=th)).json()
    assert mine[0]["id"] == doc["id"] and mine[0]["listing"] == listing["title"]
    assert (await client.get(f"/api/v1/legal/agreements/{doc['id']}/file", headers=th)).content == PDF
    # admin desk
    desk = (await client.get("/api/v1/admin/legal", headers=ah)).json()
    row = next(x for x in desk["lawyers"] if x["id"] == lawyer["id"])
    assert row["cases"] == 1 and row["agreements"] == 1 and row["passwordSet"] is True
    assert (await client.get("/api/v1/admin/overview", headers=ah)).json()["users"]["lawyers"] >= 1
    # suspended lawyers disappear and can't be messaged
    await client.post(f"/api/v1/admin/users/{lawyer['id']}/ban", headers=ah, json={"reason": "Licence suspended"})
    assert all(c["id"] != lawyer["id"] for c in (await client.get("/api/v1/lawyers", headers=oh)).json())
    blocked = await client.post(f"/api/v1/legal/cases/{cid}/messages", headers=oh, json={"text": "Hello?"})
    assert blocked.status_code == 409
    # the owner keeps the documents
    assert (await client.get(f"/api/v1/legal/agreements/{doc['id']}/file", headers=oh)).status_code == 200


async def test_admin_resets_lawyer_password(client):
    ah = await admin_headers(client)
    lawyer, lh, creds, _ = await approved_lawyer(client, ah)
    res = await client.post(f"/api/v1/admin/legal/lawyers/{lawyer['id']}/reset-password", headers=ah)
    new = res.json()["credentials"]
    assert new["username"] == creds["username"] and new["password"] != creds["password"]
    assert (await client.get("/api/v1/users/me", headers=lh)).status_code == 401
    ok = await client.post("/api/v1/auth/password-login", json={"identifier": new["username"], "password": new["password"]})
    assert ok.json()["user"]["mustChangePassword"] is True


async def test_deleting_a_lawyer_removes_their_documents(client):
    ah = await admin_headers(client)
    lawyer, _, _, data = await approved_lawyer(client, ah)
    ref = next(a["reference"] for a in (await client.get("/api/v1/admin/legal", headers=ah)).json()["applications"]
               if a["userId"] == lawyer["id"])
    assert (await client.delete(f"/api/v1/admin/users/{lawyer['id']}", headers=ah)).status_code == 200
    desk = (await client.get("/api/v1/admin/legal", headers=ah)).json()
    assert all(x["id"] != lawyer["id"] for x in desk["lawyers"])
    app = next(a for a in desk["applications"] if a["reference"] == ref)
    assert app["email"] != data["email"] and app["status"] == "approved"
    assert (await client.get(f"/api/v1/admin/legal/applications/{ref}/id", headers=ah)).status_code == 410
