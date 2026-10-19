"""Admin Routes - Dashboard & Management"""

from functools import wraps
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.admin import bp


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Akses ditolak. Hanya admin.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    return render_template('dashboard/ringkasan.html')


@bp.route('/pesanan')
@login_required
@admin_required
def pesanan():
    return render_template('dashboard/pesanan.html')


@bp.route('/produk')
@login_required
@admin_required
def produk():
    return render_template('dashboard/produk.html')


@bp.route('/pelanggan')
@login_required
@admin_required
def pelanggan():
    return render_template('dashboard/pelanggan.html')


@bp.route('/laporan')
@login_required
@admin_required
def laporan():
    return render_template('dashboard/laporan.html')


@bp.route('/ulasan')
@login_required
@admin_required
def ulasan():
    return render_template('dashboard/ulasan.html')


@bp.route('/pengaturan')
@login_required
@admin_required
def pengaturan():
    return render_template('dashboard/pengaturan.html')