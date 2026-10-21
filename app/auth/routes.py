"""Auth Routes - Login, Register, Logout"""

from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app import db
from app.models import User
from app.security_logging import log_auth_event


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
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
            user = User(fullname=fullname, username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Akun berhasil dibuat! Silakan login.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('register.html')


@bp.route('/logout', methods=['GET', 'POST'])
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