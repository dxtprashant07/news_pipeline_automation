"""Send OTP emails via SMTP (Gmail or any STARTTLS provider)."""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("dashboard.email")


def send_otp(to_email: str, otp: str, purpose: str = "account setup") -> bool:
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP not configured — OTP not sent. Code: %s", otp)
        return False

    sender = settings.smtp_from or settings.smtp_user
    subject = "Your News Pipeline verification code"

    html = f"""
    <div style="font-family:Inter,system-ui,sans-serif;background:#0d1117;padding:40px 20px;min-height:100vh;">
      <div style="max-width:480px;margin:0 auto;background:#161b27;border:1px solid rgba(255,255,255,0.07);border-radius:14px;overflow:hidden;">
        <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px;">
          <div style="font-size:1.1rem;font-weight:700;color:white;letter-spacing:-0.02em;">📰 News Pipeline</div>
          <div style="font-size:0.8rem;color:rgba(255,255,255,0.7);margin-top:4px;">Editor Dashboard</div>
        </div>
        <div style="padding:32px;">
          <h2 style="color:#e6edf3;font-size:1.1rem;font-weight:700;margin:0 0 8px;">Verification code</h2>
          <p style="color:#8b949e;font-size:0.85rem;margin:0 0 24px;line-height:1.6;">
            Use the code below to complete your <strong style="color:#e6edf3;">{purpose}</strong>.
            It expires in <strong style="color:#e6edf3;">15 minutes</strong>.
          </p>
          <div style="background:#0d1117;border:1px solid rgba(99,102,241,0.3);border-radius:10px;padding:20px;text-align:center;margin-bottom:24px;">
            <span style="font-size:2.2rem;font-weight:800;letter-spacing:0.18em;color:#6366f1;font-family:monospace;">{otp}</span>
          </div>
          <p style="color:#484f58;font-size:0.75rem;line-height:1.6;margin:0;">
            If you didn't request this, you can safely ignore this email.
            Do not share this code with anyone.
          </p>
        </div>
      </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
            s.sendmail(sender, [to_email], msg.as_string())
        logger.info("OTP sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send OTP to %s: %s", to_email, exc)
        return False
