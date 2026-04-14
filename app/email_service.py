"""
app/email_service.py
────────────────────
Async email notification service using Python's built-in smtplib.
No extra pip packages required.

Configure in .env:
    MAIL_SERVER=smtp.gmail.com
    MAIL_PORT=587
    MAIL_USE_TLS=True
    MAIL_USERNAME=your@gmail.com
    MAIL_PASSWORD=your-app-password    ← Gmail App Password
    MAIL_DEFAULT_SENDER=noreply@mefportal.edu

When MAIL_USERNAME is empty, ALL send calls are silently skipped —
safe for local development with no SMTP config.
"""

import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("mefportal")

# ── Config (read once at import) ─────────────────────────────────────────────
_MAIL_SERVER  = os.environ.get("MAIL_SERVER",  "smtp.gmail.com")
_MAIL_PORT    = int(os.environ.get("MAIL_PORT", "587"))
_MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
_MAIL_USER    = os.environ.get("MAIL_USERNAME", "")
_MAIL_PASS    = os.environ.get("MAIL_PASSWORD", "")
_MAIL_FROM    = os.environ.get("MAIL_DEFAULT_SENDER", "") or _MAIL_USER


def _send_now(to: str, subject: str, html: str, text: str) -> None:
    """Synchronous send — runs inside a background daemon thread."""
    if not _MAIL_USER or not _MAIL_PASS:
        logger.debug("Email skipped (MAIL_USERNAME not set): subject=%s to=%s", subject, to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = _MAIL_FROM
    msg["To"]      = to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    try:
        if _MAIL_USE_TLS:
            srv = smtplib.SMTP(_MAIL_SERVER, _MAIL_PORT, timeout=10)
            srv.ehlo()
            srv.starttls()
        else:
            srv = smtplib.SMTP_SSL(_MAIL_SERVER, _MAIL_PORT, timeout=10)
        srv.login(_MAIL_USER, _MAIL_PASS)
        srv.sendmail(_MAIL_USER, [to], msg.as_string())
        srv.quit()
        logger.info("Email sent subject=%s to=%s", subject, to)
    except Exception:
        logger.exception("Failed to send email subject=%s to=%s", subject, to)


def send_async(to: str, subject: str, html: str, text: str = "") -> None:
    """Fire-and-forget: send email in a daemon background thread."""
    if not to:
        return
    threading.Thread(
        target=_send_now,
        args=(to, subject, html, text or "Please view this email in an HTML-capable client."),
        daemon=True,
    ).start()


# ── Notification helpers ─────────────────────────────────────────────────────

def notify_submitted(student_email: str, student_name: str, req_type: str, req_id: int) -> None:
    """Notify student that their request was submitted successfully."""
    subject = f"[MEF Portal] {req_type} request submitted (#{req_id})"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:8px">
      <h2 style="color:#4f46e5">✅ Request Submitted</h2>
      <p>Dear <strong>{student_name}</strong>,</p>
      <p>Your <strong>{req_type}</strong> request (ID: <code>#{req_id}</code>) has been submitted
      and is <em>pending Mentor review</em>.</p>
      <p>You will receive an email whenever the status changes.</p>
      <p style="color:#64748b;font-size:0.875em">— MEF Portal, Selvam College of Technology</p>
    </div>"""
    text = f"Dear {student_name}, your {req_type} request #{req_id} has been submitted for review."
    send_async(student_email, subject, html, text)


def notify_status_changed(
    student_email: str,
    student_name: str,
    req_type: str,
    req_id: int,
    new_status: str,
    actor_name: str,
    note: Optional[str] = None,
) -> None:
    """Notify student when any approver acts on their request."""
    emoji = "✅" if "Approved" in new_status else "❌" if "Rejected" in new_status else "🔄"
    subject = f"[MEF Portal] {emoji} {req_type} #{req_id} — {new_status}"
    note_html = f"<p><strong>Reviewer note:</strong> {note}</p>" if note else ""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:8px">
      <h2 style="color:#4f46e5">{emoji} Request Update</h2>
      <p>Dear <strong>{student_name}</strong>,</p>
      <p>Your <strong>{req_type}</strong> request (ID: <code>#{req_id}</code>)
      has been <strong>{new_status}</strong> by <em>{actor_name}</em>.</p>
      {note_html}
      <p>Log in to the <a href="#" style="color:#4f46e5">MEF Portal</a> to view details
      {"and download your approval letter." if new_status == "Approved" else "."}</p>
      <p style="color:#64748b;font-size:0.875em">— MEF Portal, Selvam College of Technology</p>
    </div>"""
    text = f"Dear {student_name}, your {req_type} request #{req_id} status is now: {new_status}."
    send_async(student_email, subject, html, text)


def send_password_reset(to_email: str, name: str, reset_url: str) -> None:
    """Send password reset link."""
    subject = "[MEF Portal] Password Reset Request"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:8px">
      <h2 style="color:#4f46e5">🔑 Password Reset</h2>
      <p>Dear <strong>{name}</strong>,</p>
      <p>You (or someone else) requested a password reset for your MEF Portal account.</p>
      <p><a href="{reset_url}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;border-radius:6px;text-decoration:none;font-weight:bold">Reset My Password</a></p>
      <p>This link expires in <strong>30 minutes</strong>.
      If you did not request this, simply ignore this email — your password will not change.</p>
      <p style="color:#64748b;font-size:0.875em">— MEF Portal, Selvam College of Technology</p>
    </div>"""
    text = f"Dear {name}, reset your password at: {reset_url}  (expires in 30 minutes)."
    send_async(to_email, subject, html, text)
