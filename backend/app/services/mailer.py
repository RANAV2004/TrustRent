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
def build_reset_email(to: str, code: str, minutes: int) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"{code} is your TrustRent password reset code"
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL or settings.SMTP_USER))
    msg["To"] = to
    msg.set_content(
        f"Someone asked to reset the password of your TrustRent account. Your code is {code}.\n\n"
        f"It expires in {minutes} minutes. Don't share it with anyone: TrustRent will never ask you for it.\n\n"
        "If this wasn't you, ignore this email: your password stays the same."
    )
    msg.add_alternative(f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:420px;margin:auto;color:#1b1b1b">
  <p style="font-size:18px;font-weight:bold;margin:0 0 16px">TrustRent</p>
  <p>Enter this code to choose a new password:</p>
  <p style="font-size:32px;font-weight:bold;letter-spacing:6px;margin:8px 0 16px">{code}</p>
  <p>It expires in {minutes} minutes. Don't share it with anyone: TrustRent will never ask you for it.</p>
  <p style="color:#6b6b6b;font-size:13px">If this wasn't you, ignore this email: your password stays the same.</p>
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
async def send_reset_email(to: str, code: str, minutes: int = 10) -> None:
    try:
        await asyncio.to_thread(_send, build_reset_email(to, code, minutes))
    except (smtplib.SMTPException, OSError) as e:
        log.error("Sending the password reset code failed: %s", e)
        raise EmailError("We couldn't send the email. Try again in a minute.") from e

def _simple_email(to: str, subject: str, lines: list[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL or settings.SMTP_USER))
    msg["To"] = to
    msg.set_content("\n\n".join(lines))
    return msg
def build_lawyer_approved_email(to: str, name: str, username: str, password: str) -> EmailMessage:
    where = f"Sign in at {settings.APP_URL.rstrip('/')}/lawyer-login" if settings.APP_URL else "Sign in on the TrustRent website (Lawyer link on the sign-in page)"
    return _simple_email(to, "Your TrustRent lawyer account is ready", [
        f"Hello {name},",
        "We've verified your details and your TrustRent lawyer account is ready.",
        f"{where} with:\nUsername: {username}\nTemporary password: {password}",
        "You'll be asked to choose your own password the first time you sign in. Don't share these details.",
        "TrustRent",
    ])
def build_lawyer_rejected_email(to: str, name: str, reference: str, note: str) -> EmailMessage:
    return _simple_email(to, "About your TrustRent lawyer application", [
        f"Hello {name},",
        f"We couldn't verify your lawyer application {reference}.",
        f"Reason: {note}",
        "You're welcome to apply again with the corrected details or documents.",
        "TrustRent",
    ])
async def send_message_email(msg: EmailMessage) -> None:  # best effort: callers decide what to do on failure
    try:
        await asyncio.to_thread(_send, msg)
    except (smtplib.SMTPException, OSError) as e:
        log.error("Sending %r to %s failed: %s", msg["Subject"], msg["To"], e)
        raise EmailError("We couldn't send the email.") from e
