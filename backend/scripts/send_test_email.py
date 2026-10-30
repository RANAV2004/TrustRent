import asyncio
import secrets
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings  # noqa: E402
from app.services.mailer import EmailError, email_enabled, send_code_email  # noqa: E402
def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/send_test_email.py you@example.com")
        return 2
    if not email_enabled():
        print("SMTP_USER or SMTP_APP_PASSWORD is empty. Add them to .env first.")
        return 1
    print(f"Sending a test code from {settings.SMTP_USER} via {settings.SMTP_HOST}:{settings.SMTP_PORT} ...")
    try:
        code = f"{secrets.randbelow(10**6):06d}"
        asyncio.run(send_code_email(sys.argv[1], code))
    except EmailError as e:
        print("FAILED:", e.__cause__ or e)
        print("Check the app password (16 letters, no spaces) and that 2-Step Verification is on.")
        return 1
    print(f"Sent code {code}. Check the inbox (and spam) of {sys.argv[1]}.")
    return 0
if __name__ == "__main__":
    sys.exit(main())
