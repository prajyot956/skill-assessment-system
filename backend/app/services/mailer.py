import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send via SMTP if configured; otherwise write the message to the server log.
    Returns True only when an email was actually handed to an SMTP server."""
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        log.warning("SMTP not configured. Email to %s not sent.\nSubject: %s\n%s", to, subject, body)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["SMTP_FROM"], to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as smtp:
            smtp.starttls()
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"] or "")
            smtp.send_message(msg)
        return True
    except Exception:  # never leak SMTP details to the client
        log.exception("Failed to send email to %s", to)
        return False
