import base64
import hashlib
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode
import httpx
from defusedxml import ElementTree
from app.core.config import settings


class DigilockerError(Exception):
    pass


def enabled() -> bool:
    return bool(settings.DIGILOCKER_CLIENT_ID and settings.DIGILOCKER_CLIENT_SECRET and settings.DIGILOCKER_REDIRECT_URI)


def new_pkce() -> tuple[str, str, str]:
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return state, verifier, challenge


def authorize_url(state: str, challenge: str) -> str:
    q = {"response_type": "code", "client_id": settings.DIGILOCKER_CLIENT_ID, "redirect_uri": settings.DIGILOCKER_REDIRECT_URI,
         "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}
    return f"{settings.DIGILOCKER_AUTHORIZE_URL}?{urlencode(q)}"


SESSION_MINUTES = 10
SESSION_TTL = timedelta(minutes=SESSION_MINUTES)


async def fetch_eaadhaar(code: str, verifier: str) -> bytes:
    data = {"code": code, "grant_type": "authorization_code", "client_id": settings.DIGILOCKER_CLIENT_ID,
            "client_secret": settings.DIGILOCKER_CLIENT_SECRET, "redirect_uri": settings.DIGILOCKER_REDIRECT_URI,
            "code_verifier": verifier}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            tok = await client.post(settings.DIGILOCKER_TOKEN_URL, data=data)
            if tok.status_code >= 400 or "access_token" not in tok.json():
                raise DigilockerError("DigiLocker didn't accept the sign-in. Try again.")
            res = await client.get(settings.DIGILOCKER_EAADHAAR_URL,
                                   headers={"Authorization": f"Bearer {tok.json()['access_token']}"})
    except (httpx.HTTPError, ValueError) as e:
        raise DigilockerError("Couldn't reach DigiLocker. Try again in a minute.") from e
    if res.status_code >= 400 or not res.content:
        raise DigilockerError("DigiLocker didn't share your Aadhaar. Allow access to Aadhaar and try again.")
    return res.content


def parse_eaadhaar(xml: bytes) -> dict:
    """Name, date of birth and the last 4 Aadhaar digits only. Nothing else is kept."""
    try:
        root = ElementTree.fromstring(xml)
    except Exception as e:  # noqa: BLE001 - defusedxml raises several types
        raise DigilockerError("DigiLocker sent an Aadhaar file we can't read.") from e
    name = dob = uid = None
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "Poi":
            name, dob = el.attrib.get("name"), el.attrib.get("dob")
        if tag == "UidData" and el.attrib.get("uid"):
            uid = el.attrib["uid"]
    if not name:
        raise DigilockerError("Your DigiLocker Aadhaar has no name on it.")
    digits = re.sub(r"\D", "", uid or "")
    return {"name": name.strip(), "dob": dob, "last4": digits[-4:] if digits else None}


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z]+", (s or "").lower()) if len(t) > 1}


def names_match(account_first: str, account_last: str, aadhaar_name: str) -> bool:
    mine, theirs = _tokens(f"{account_first} {account_last}"), _tokens(aadhaar_name)
    return bool(mine) and mine <= theirs
