import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from app.core.config import settings
log = logging.getLogger(__name__)
class EmailError(Exception):
    pass
def email_enabled() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_APP_PASSWORD)
def build_code_email(to: str, code: str, minutes: int) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"{code} is your TrustRent verification code"
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL or settings.SMTP_USER))
    msg["To"] = to
    msg.set_content(
        f"Your TrustRent verification code is {code}. Enter it to finish creating your account.\n\n"
        f"It expires in {minutes} minutes. Don't share it with anyone: TrustRent will never ask you for it.\n\n"
        "If you didn't sign up for TrustRent, you can ignore this email."
    )
    msg.add_alternative(f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:420px;margin:auto;color:#1b1b1b">
  <p style="font-size:18px;font-weight:bold;margin:0 0 16px">TrustRent</p>
  <p>Enter this code to verify your email and finish creating your account:</p>
  <p style="font-size:32px;font-weight:bold;letter-spacing:6px;margin:8px 0 16px">{code}</p>
  <p>It expires in {minutes} minutes. Don't share it with anyone: TrustRent will never ask you for it.</p>
  <p style="color:#6b6b6b;font-size:13px">If you didn't sign up for TrustRent, you can ignore this email.</p>
</div>""", subtype="html")
    return msg
def _send(msg: EmailMessage) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(settings.SMTP_USER, settings.SMTP_APP_PASSWORD)
        smtp.send_message(msg)
async def send_code_email(to: str, code: str, minutes: int = 10) -> None:
    try:
        await asyncio.to_thread(_send, build_code_email(to, code, minutes))
    except smtplib.SMTPAuthenticationError as e:
        log.error("SMTP login failed for %s: check SMTP_USER and SMTP_APP_PASSWORD (%s)", settings.SMTP_USER, e)
        raise EmailError("We couldn't send the email right now. Try again later.") from e
    except (smtplib.SMTPException, OSError) as e:
        log.error("Sending the verification code failed: %s", e)
        raise EmailError("We couldn't send the email. Try again in a minute.") from e