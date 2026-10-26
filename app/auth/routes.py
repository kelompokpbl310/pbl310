"""Auth Routes - Login, Register, Logout, OTP Verification"""

from flask import render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app import db
from app.models import User, EmailOTP
from app.security_logging import log_auth_event
from app.auth.helpers import (
    generate_otp_code, hash_otp_code, check_otp_code,
    create_otp, send_otp_email, get_pending_otp,
    count_recent_sends, mask_email,
    OTP_MAX_ATTEMPTS, RESEND_COOLDOWN_SECONDS, RESEND_MAX_PER_HOUR,
)
from datetime import datetime, timedelta, timezone


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                log_auth_event(
                    event='login_blocked_inactive',
                    user_id=user.id,
                    username=user.username,
                    role=user.role,
                    status='failure',
                    reason='Account is inactive'
                )
                flash('Akun Anda dinonaktifkan. Silakan hubungi admin.', 'error')
                return render_template('login.html')

            # Admin accounts are unaffected by email verification
            if user.role != 'admin' and not user.email_verified:
                # Send a fresh OTP if cooldown allows
                cooldown_ok = True
                since = datetime.now(timezone.utc) - timedelta(hours=1)
                otp_count = EmailOTP.query.filter(
                    EmailOTP.user_id == user.id,
                    EmailOTP.purpose == 'register',
                    EmailOTP.created_at >= since,
                ).count()
                if otp_count >= RESEND_MAX_PER_HOUR:
                    cooldown_ok = False
                # Check cooldown: last OTP created_at
                last_otp = EmailOTP.query.filter_by(
                    user_id=user.id, purpose='register'
                ).order_by(EmailOTP.created_at.desc()).first()
                if last_otp:
                    created = last_otp.created_at
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - created).total_seconds()
                    if elapsed < RESEND_COOLDOWN_SECONDS:
                        cooldown_ok = False

                if cooldown_ok:
                    otp, code = create_otp(user.id, purpose='register')
                    success, err = send_otp_email(user.email, code)
                    if success:
                        log_auth_event(
                            event='otp_sent',
                            user_id=user.id,
                            username=user.username,
                            role=user.role,
                            status='success',
                            reason='login_unverified'
                        )
                    else:
                        flash(err or 'Gagal mengirim email verifikasi.', 'error')
                else:
                    # cooldown not ok, but still show message
                    pass

                session['pending_verify_user_id'] = user.id
                log_auth_event(
                    event='login_blocked_unverified',
                    user_id=user.id,
                    username=user.username,
                    role=user.role,
                    status='failure',
                    reason='Email not verified'
                )
                flash('Email Anda belum diverifikasi. Silakan verifikasi terlebih dahulu.', 'warning')
                return redirect(url_for('auth.verify'))

            login_user(user)
            # Log successful login - both admin and regular user
            if user.role == 'admin':
                log_auth_event(
                    event='admin_login_success',
                    user_id=user.id,
                    username=user.username,
                    role=user.role,
                    status='success'
                )
            else:
                log_auth_event(
                    event='user_login_success',
                    user_id=user.id,
                    username=user.username,
                    role=user.role,
                    status='success'
                )
            next_page = request.args.get('next')
            if user.role == 'admin':
                return redirect(next_page or url_for('admin.dashboard'))
            return redirect(next_page or url_for('main.index'))
        else:
            # Log failed login attempt
            reason = 'invalid_credentials' if user else 'user_not_found'
            log_auth_event(
                event='login_failed',
                username=username,
                status='failure',
                reason=reason,
                level=30  # WARNING
            )
            flash('Username atau password salah.', 'error')

    return render_template('login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if password != confirm:
            flash('Password dan konfirmasi tidak cocok.', 'error')
        elif len(password) < 6:
            flash('Password minimal 6 karakter.', 'error')
        elif not email:
            flash('Email wajib diisi.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username sudah terdaftar.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email sudah terdaftar.', 'error')
        else:
            user = User(fullname=fullname, username=username, email=email, email_verified=False)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Generate OTP
            otp, code = create_otp(user.id, purpose='register')

            # Send email
            success, err = send_otp_email(user.email, code)
            if success:
                log_auth_event(
                    event='otp_sent',
                    user_id=user.id,
                    username=user.username,
                    role=user.role,
                    status='success',
                    reason='registration'
                )
            else:
                flash(err or 'Gagal mengirim email verifikasi.', 'error')

            # Store pending user id in session
            session['pending_verify_user_id'] = user.id

            flash('Akun berhasil dibuat! Silakan verifikasi email Anda.', 'success')
            return redirect(url_for('auth.verify'))

    return render_template('register.html')


@bp.route('/verifikasi', methods=['GET', 'POST'])
def verify():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user_id = session.get('pending_verify_user_id')
    if not user_id:
        flash('Sesi verifikasi tidak ditemukan. Silakan login atau daftar ulang.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user:
        session.pop('pending_verify_user_id', None)
        flash('Pengguna tidak ditemukan.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code or len(code) != 6 or not code.isdigit():
            flash('Kode harus 6 digit angka.', 'error')
            return render_template('verifikasi.html', user=user, masked_email=mask_email(user.email))

        otp = get_pending_otp(user.id, purpose='register')
        if otp is None:
            flash('Kode OTP tidak valid atau sudah kedaluwarsa. Silakan kirim ulang.', 'error')
            return render_template('verifikasi.html', user=user, masked_email=mask_email(user.email))

        # Check expiry
        now = datetime.now(timezone.utc)
        expires = otp.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            flash('Kode OTP sudah kedaluwarsa. Silakan kirim ulang.', 'error')
            return render_template('verifikasi.html', user=user, masked_email=mask_email(user.email))

        # Check consumed
        if otp.consumed_at is not None:
            flash('Kode OTP sudah digunakan. Silakan kirim ulang.', 'error')
            return render_template('verifikasi.html', user=user, masked_email=mask_email(user.email))

        # Check attempts
        if otp.attempts >= OTP_MAX_ATTEMPTS:
            # Invalidate
            otp.consumed_at = datetime.now(timezone.utc)
            db.session.commit()
            log_auth_event(
                event='otp_locked',
                user_id=user.id,
                username=user.username,
                role=user.role,
                status='failure',
                reason='Max attempts exceeded'
            )
            flash('Terlalu banyak percobaan. Silakan kirim ulang kode.', 'error')
            return render_template('verifikasi.html', user=user, masked_email=mask_email(user.email))

        # Verify code
        if check_otp_code(otp.code_hash, code):
            otp.consumed_at = datetime.now(timezone.utc)
            user.email_verified = True
            db.session.commit()
            log_auth_event(
                event='otp_verified',
                user_id=user.id,
                username=user.username,
                role=user.role,
                status='success'
            )
            session.pop('pending_verify_user_id', None)
            login_user(user)
            flash('Email berhasil diverifikasi! Selamat datang.', 'success')
            return redirect(url_for('main.index'))
        else:
            otp.attempts += 1
            db.session.commit()
            log_auth_event(
                event='otp_failed',
                user_id=user.id,
                username=user.username,
                role=user.role,
                status='failure',
                reason='Wrong code'
            )
            remaining = OTP_MAX_ATTEMPTS - otp.attempts
            if remaining <= 0:
                otp.consumed_at = datetime.now(timezone.utc)
                db.session.commit()
                log_auth_event(
                    event='otp_locked',
                    user_id=user.id,
                    username=user.username,
                    role=user.role,
                    status='failure',
                    reason='Max attempts exceeded'
                )
                flash('Terlalu banyak percobaan. Silakan kirim ulang kode.', 'error')
            else:
                flash(f'Kode salah. Sisa percobaan: {remaining}.', 'error')
            return render_template('verifikasi.html', user=user, masked_email=mask_email(user.email))

    return render_template('verifikasi.html', user=user, masked_email=mask_email(user.email))


@bp.route('/verifikasi/kirim-ulang', methods=['POST'])
def resend_otp():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user_id = session.get('pending_verify_user_id')
    if not user_id:
        flash('Sesi verifikasi tidak ditemukan.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user:
        session.pop('pending_verify_user_id', None)
        flash('Pengguna tidak ditemukan.', 'error')
        return redirect(url_for('auth.login'))

    # Rate limit: max 5 sends per hour
    recent_count = count_recent_sends(user.id, purpose='register', hours=1)
    if recent_count >= RESEND_MAX_PER_HOUR:
        log_auth_event(
            event='otp_locked',
            user_id=user.id,
            username=user.username,
            role=user.role,
            status='failure',
            reason='Resend rate limit exceeded'
        )
        flash('Terlalu banyak permintaan. Coba lagi nanti.', 'error')
        return redirect(url_for('auth.verify'))

    # Cooldown: 60 seconds
    last_otp = EmailOTP.query.filter_by(
        user_id=user.id, purpose='register'
    ).order_by(EmailOTP.created_at.desc()).first()
    if last_otp:
        created = last_otp.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - created).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            flash('Tunggu sebentar sebelum mengirim ulang.', 'error')
            return redirect(url_for('auth.verify'))

    # Invalidate older unused OTPs
    EmailOTP.query.filter_by(
        user_id=user.id, purpose='register', consumed_at=None
    ).update({'consumed_at': datetime.now(timezone.utc)})
    db.session.commit()

    # Create new OTP
    otp, code = create_otp(user.id, purpose='register')
    success, err = send_otp_email(user.email, code)
    if success:
        log_auth_event(
            event='otp_resent',
            user_id=user.id,
            username=user.username,
            role=user.role,
            status='success'
        )
        flash('Kode baru telah dikirim.', 'success')
    else:
        flash(err or 'Gagal mengirim email.', 'error')

    return redirect(url_for('auth.verify'))


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = current_user.id
    username = current_user.username
    role = current_user.role
    logout_user()
    log_auth_event(
        event='user_logout',
        user_id=user_id,
        username=username,
        role=role,
        status='success'
    )
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('main.index'))



