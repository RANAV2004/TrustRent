import pytest
import uuid
import io
from httpx import AsyncClient, ASGITransport
from app.main import app
@pytest.mark.asyncio
async def test_full_api_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/health")
        assert res.status_code == 200
        landlord_email = f"landlord_{uuid.uuid4().hex[:6]}@example.com"
        res = await ac.post("/api/v1/auth/login", json={
            "email": landlord_email,
            "name": "Landlord Test",
            "role": "landlord",
            "smart_account_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        })
        assert res.status_code == 200
        landlord_token = res.json()["access_token"]
        landlord_headers = {"Authorization": f"Bearer {landlord_token}"}
        tenant_email = f"tenant_{uuid.uuid4().hex[:6]}@example.com"
        res = await ac.post("/api/v1/auth/login", json={
            "email": tenant_email,
            "name": "Tenant Test",
            "role": "tenant",
            "smart_account_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
        })
        assert res.status_code == 200
        tenant_token = res.json()["access_token"]
        tenant_headers = {"Authorization": f"Bearer {tenant_token}"}
        res = await ac.get("/api/v1/auth/me", headers=landlord_headers)
        assert res.status_code == 200
        assert res.json()["email"] == landlord_email
        res = await ac.post("/api/v1/identity/verify", headers=tenant_headers, json={
            "full_name": "Tenant Test",
            "id_type": "AADHAAR",
            "id_number": "1234-5678-9012",
            "phone": "+91-9876543210"
        })
        assert res.status_code == 200
        attestation = res.json()
        assert attestation["verified"] is True
        assert attestation["attestation_hash"].startswith("0x")
        dummy_pdf = io.BytesIO(b"%PDF-1.4 LEASE AGREEMENT TEST")
        res = await ac.post(
            "/api/v1/tenancies/draft",
            headers=landlord_headers,
            data={
                "property_address": "Flat 402, Lotus Court, Indore",
                "monthly_rent": "25000",
                "deposit_amount": "50000",
                "deduction_cap": "20000",
                "claim_window_days": "7",
                "tenant_email": tenant_email
            },
            files={"lease_file": ("lease.pdf", dummy_pdf, "application/pdf")}
        )
        assert res.status_code == 200
        draft_data = res.json()
        tenancy_id = draft_data["tenancy_id"]
        assert draft_data["lease_hash"].startswith("0x")
        photo_bytes = io.BytesIO(b"JPEG_MOVE_IN_LIVING_ROOM_IMAGE_BYTES")
        res = await ac.post(
            "/api/v1/evidence/upload",
            headers=tenant_headers,
            data={
                "tenancy_id": tenancy_id,
                "evidence_type": "move_in"
            },
            files={"file": ("move_in_1.jpg", photo_bytes, "image/jpeg")}
        )
        assert res.status_code == 200
        evidence_id = res.json()["evidence_id"]
        assert res.json()["file_hash"].startswith("0x")
        res = await ac.get(f"/api/v1/evidence/{evidence_id}/verify", headers=tenant_headers)
        assert res.status_code == 200
        assert res.json()["matches"] is True
        assert res.json()["status"] == "VALID_TAMPER_FREE"
        res = await ac.get(f"/api/v1/evidence/{evidence_id}/download", headers=landlord_headers)
        assert res.status_code == 200
        assert res.content == b"JPEG_MOVE_IN_LIVING_ROOM_IMAGE_BYTES"
        res = await ac.post("/api/v1/faucet/", headers=tenant_headers, json={
            "recipient_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
        })
        assert res.status_code == 200
        assert res.json()["success"] is True
