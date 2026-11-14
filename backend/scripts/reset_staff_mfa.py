"""Turn off two-step sign-in for a staff account that lost its authenticator app.

Run on the server (it uses DATABASE_URL from .env):  python scripts/reset_staff_mfa.py admin@trustrent.in
The next password sign-in shows a new setup key. All of that account's sessions are signed out.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import func, select  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


async def main(email: str) -> int:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if not user:
            print(f"No account with email {email}")
            return 1
        user.totp_secret, user.totp_enabled, user.totp_last_step = None, False, None
        user.token_version = (user.token_version or 0) + 1
        await db.commit()
        print(f"Two-step sign-in reset for {email}. They set it up again at their next sign-in.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
