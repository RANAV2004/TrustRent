"""Aadhaar eSign through Digio. Only this file talks to the provider; check field names against your Digio sandbox."""
import base64
import httpx
from fpdf import FPDF
from app.core.config import settings


class EsignError(Exception):
    pass


def enabled() -> bool:
    return settings.ESIGN_PROVIDER == "digio" and bool(settings.DIGIO_CLIENT_ID and settings.DIGIO_CLIENT_SECRET)


def _latin(s: str) -> str:
    return (s or "").replace("₹", "Rs ").replace("’", "'").replace("—", "-").encode("latin-1", "replace").decode("latin-1")


def agreement_pdf(text: str, footer: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Times", size=11)
    for i, para in enumerate(text.split("\n\n")):
        if i == 0:
            pdf.set_font("Times", "B", 14)
        pdf.multi_cell(0, 6, _latin(para))
        pdf.ln(2)
        if i == 0:
            pdf.set_font("Times", size=11)
    pdf.ln(4)
    pdf.set_font("Times", "I", 8)
    pdf.multi_cell(0, 4, _latin(footer))
    return bytes(pdf.output())


def _auth():
    return (settings.DIGIO_CLIENT_ID, settings.DIGIO_CLIENT_SECRET)


async def create_request(pdf: bytes, file_name: str, signers: list[dict]) -> str:
    body = {
        "signers": [{"identifier": s["identifier"], "name": s["name"], "sign_type": "aadhaar", "reason": "Rent agreement"} for s in signers],
        "expire_in_days": 10, "display_on_page": "last", "notify_signers": True, "send_sign_link": True,
        "file_name": file_name, "file_data": base64.b64encode(pdf).decode(),
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(f"{settings.DIGIO_BASE_URL}/v2/client/document/uploadpdf", json=body, auth=_auth())
    except httpx.HTTPError as e:
        raise EsignError("Couldn't reach the eSign service. Try again.") from e
    if res.status_code >= 400 or not res.json().get("id"):
        raise EsignError("The eSign service refused the document.")
    return res.json()["id"]


def is_complete(doc: dict) -> bool:
    if str(doc.get("agreement_status", "")).lower() == "completed":
        return True
    parties = doc.get("signing_parties") or []
    return bool(parties) and all(str(p.get("status", "")).lower() == "signed" for p in parties)


async def fetch(doc_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.get(f"{settings.DIGIO_BASE_URL}/v2/client/document/{doc_id}", auth=_auth())
    except httpx.HTTPError as e:
        raise EsignError("Couldn't reach the eSign service.") from e
    if res.status_code >= 400:
        raise EsignError("The eSign service didn't find this document.")
    return res.json()


async def download(doc_id: str) -> bytes:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.get(f"{settings.DIGIO_BASE_URL}/v2/client/document/download", params={"document_id": doc_id}, auth=_auth())
    except httpx.HTTPError as e:
        raise EsignError("Couldn't download the signed document.") from e
    if res.status_code >= 400 or not res.content.startswith(b"%PDF"):
        raise EsignError("The signed document isn't ready yet.")
    return res.content


def sign_link(doc_id: str, identifier: str) -> str | None:
    tpl = settings.DIGIO_SIGN_URL
    if not tpl:  # the provider emails each signer their own link
        return None
    return tpl.format(document_id=doc_id, identifier=identifier)
