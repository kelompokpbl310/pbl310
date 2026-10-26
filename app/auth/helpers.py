"""Auth helpers - OTP generation, email sending, security logging."""

import os
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from app import db
from app.models import EmailOTP



OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
RESEND_MAX_PER_HOUR = 5


def generate_otp_code():
    """Generate a 6-digit OTP code using secrets module."""
    return f'{secrets.randbelow(1000000):06d}'


def hash_otp_code(code):
    """Hash an OTP code using werkzeug generate_password_hash."""
    return generate_password_hash(code)


def check_otp_code(code_hash, code):
    """Check an OTP code against its hash."""
    return check_password_hash(code_hash, code)


def create_otp(user_id, purpose='register'):
    """Create and store a new OTP for a user. Invalidate older unused OTPs."""
    # Invalidate older unused OTPs
    EmailOTP.query.filter_by(
        user_id=user_id, purpose=purpose, consumed_at=None
    ).update({'consumed_at': datetime.now(timezone.utc)})

    code = generate_otp_code()
    code_hash = hash_otp_code(code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

    otp = EmailOTP(
        user_id=user_id,
        code_hash=code_hash,
        purpose=purpose,
        expires_at=expires_at,
    )
    db.session.add(otp)
    db.session.commit()
    return otp, code


def send_otp_email(email, code):
    """Send OTP email via SMTP with STARTTLS. Returns (success, error_message)."""
    if os.getenv('MAIL_SUPPRESS_SEND', 'false').lower() in ('true', '1', 'yes'):
        # Development: print code to console only
        current_app.logger.info(f'[OTP SUPPRESSED] Code for {email}: {code}')
        print(f'[OTP SUPPRESSED] Code for {email}: {code}')
        return True, None

    mail_server = os.getenv('MAIL_SERVER')
    mail_port = int(os.getenv('MAIL_PORT', '587'))
    mail_use_tls = os.getenv('MAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes')
    mail_username = os.getenv('MAIL_USERNAME')
    mail_password = os.getenv('MAIL_PASSWORD')
    mail_default_sender = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@cateringbatam.web.id')

    if not mail_server:
        current_app.logger.error('MAIL_SERVER not configured')
        return False, 'Konfigurasi email belum diatur.'

    msg = EmailMessage()
    msg['Subject'] = 'Kode Verifikasi Catering Batam'
    msg['From'] = mail_default_sender
    msg['To'] = email
    msg.set_content(
        f'Kode verifikasi Anda adalah: {code}\n\n'
        f'Kode ini berlaku selama {OTP_EXPIRY_MINUTES} menit.\n\n'
        f'Jika Anda tidak mendaftar di Catering Batam, abaikan email ini.'
    )

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
            if mail_use_tls:
                server.starttls()
            if mail_username and mail_password:
                server.login(mail_username, mail_password)
            server.send_message(msg)
        return True, None
    except Exception as e:
        current_app.logger.error(f'Failed to send OTP email: {e}')
        return False, 'Gagal mengirim email. Silakan coba lagi.'


def get_pending_otp(user_id, purpose='register'):
    """Get the latest unconsumed, non-expired OTP for a user."""
    now = datetime.now(timezone.utc)
    otp = EmailOTP.query.filter_by(
        user_id=user_id, purpose=purpose, consumed_at=None
    ).order_by(EmailOTP.created_at.desc()).first()
    if otp is None:
        return None
    expires = otp.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return None  # expired
    return otp


def count_recent_sends(user_id, purpose='register', hours=1):
    """Count OTP sends in the last hour for rate limiting."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return EmailOTP.query.filter(
        EmailOTP.user_id == user_id,
        EmailOTP.purpose == purpose,
        EmailOTP.created_at >= since,
    ).count()


def mask_email(email):
    """Mask email for display: a***@gmail.com"""
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 1:
        masked_local = local + '***'
    else:
        masked_local = local[0] + '***'
    return f'{masked_local}@{domain}'