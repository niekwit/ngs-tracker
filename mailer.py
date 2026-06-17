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


def send_alert(subject: str, body: str) -> bool:
    """Send an alert email via SMTP. Returns True on success."""
    if not get_email_alerts_enabled():
        return False

    host = get_smtp_host()
    port = get_smtp_port()
    user = get_smtp_user()
    password = get_smtp_password()
    recipient = get_alert_recipient()

    if not all([host, user, password, recipient]):
        _log.warning("Email alert skipped: incomplete SMTP configuration.")
        return False

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
        return True
    except Exception as exc:
        _log.error("Failed to send alert email: %s", exc)
        return False
