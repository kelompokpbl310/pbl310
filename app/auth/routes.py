"""Auth Routes - Login, Register, Logout"""

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app import db
from app.models import User


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
            next_page = request.args.get('next')
            if user.role == 'admin':
                return redirect(next_page or url_for('admin.dashboard'))
            return redirect(next_page or url_for('main.index'))
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
    logout_user()
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('main.index'))