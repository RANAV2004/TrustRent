"""Turn off two-step sign-in for an admin who lost their phone AND their recovery codes.

Run it on the server (Render: Shell tab) from the backend folder:
    python scripts/reset_admin_2fa.py admin@yourdomain.in
The admin then signs in with their password and sets up a new authenticator straight away.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import func, select  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.marketplace import utcnow  # noqa: E402
from app.models.user import User  # noqa: E402


async def main(email: str) -> int:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if not user:
            print(f"No account uses {email}.")
            return 1
        user.totp_secret = user.totp_pending = user.totp_enabled_at = user.totp_last_step = user.recovery_codes = None
        user.password_changed_at = utcnow()  # signs them out everywhere
        await db.commit()
        print(f"Two-step sign-in is off for {email}. They must sign in and set it up again.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
