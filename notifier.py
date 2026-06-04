"""
macOS desktop notification via osascript. No extra dependencies required.
Email alerts via Gmail SMTP — set ALERT_EMAIL and GMAIL_APP_PASSWORD in .env.
"""

import os
import smtplib
import subprocess
from email.mime.text import MIMEText


def notify(title: str, message: str) -> None:
    script = f'display notification "{message}" with title "{title}" sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True)
    except Exception as e:
        print(f"Notification failed: {e}")


def email_alert(subject: str, body: str) -> None:
    """Send an email to ALERT_EMAIL via Gmail SMTP. Silently skips if not configured."""
    to_addr = os.environ.get("ALERT_EMAIL")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not to_addr or not password:
        return
    msg = MIMEText(body)
    msg["Subject"] = f"[mackbot] {subject}"
    msg["From"] = to_addr
    msg["To"] = to_addr
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(to_addr, password)
            smtp.send_message(msg)
        print(f"Alert email sent: {subject}")
    except Exception as e:
        print(f"Email alert failed: {e}")
