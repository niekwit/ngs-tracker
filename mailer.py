import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    get_alert_recipient,
    get_email_alerts_enabled,
    get_smtp_host,
    get_smtp_password,
    get_smtp_port,
    get_smtp_user,
)

_log = logging.getLogger("ngs_tracker.mailer")


def send_alert_with_error(subject: str, body: str) -> tuple[bool, str]:
    """Send an alert email. Returns (success, error_message)."""
    if not get_email_alerts_enabled():
        return False, "Email alerts are disabled."

    host = get_smtp_host()
    port = get_smtp_port()
    user = get_smtp_user()
    password = get_smtp_password()
    recipient = get_alert_recipient()

    if not all([host, user, password, recipient]):
        return False, "Incomplete SMTP configuration — fill in all fields."

    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = recipient
        msg["Subject"] = f"[NGS Tracker] {subject}"
        msg.attach(MIMEText(body, "plain"))

        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.sendmail(user, recipient, msg.as_string())
        _log.info("Alert email sent: %s", subject)
        return True, ""
    except Exception as exc:
        _log.error("Failed to send alert email: %s", exc)
        return False, str(exc)


def send_alert(subject: str, body: str) -> bool:
    """Send an alert email. Returns True on success."""
    ok, _ = send_alert_with_error(subject, body)
    return ok
