"""Profile routes for main blueprint."""

from flask import render_template, url_for, request, redirect, flash, current_app
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Product, User, Order
from app.security_logging import log_auth_event
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime, timezone
import os
import uuid
from app.main.helpers import normalize_image_to_rgb


UPLOAD_FOLDER = 'static/uploads/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/profil')
@login_required
def profil():
    """Akun tab - Profile info + photo upload"""
    return render_template('profil/akun.html')


@bp.route('/profil', methods=['POST'])
@login_required
def profil_update():
    fullname = request.form.get('fullname', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()

    if not fullname:
        flash('Nama lengkap wajib diisi.', 'error')
        return redirect(url_for('main.profil'))

    if not email:
        flash('Email wajib diisi.', 'error')
        return redirect(url_for('main.profil'))

    # Check email uniqueness (excluding current user)
    existing = User.query.filter(User.email == email, User.id != current_user.id).first()
    if existing:
        flash('Email sudah terdaftar.', 'error')
        return redirect(url_for('main.profil'))

    current_user.fullname = fullname
    current_user.email = email
    current_user.phone = phone if phone else None

    db.session.commit()
    flash('Profil berhasil diperbarui.', 'success')
    return redirect(url_for('main.profil'))


@bp.route('/profil/photo', methods=['POST'])
@login_required
def profil_photo():
    if 'avatar' not in request.files:
        flash('Tidak ada file yang diunggah.', 'error')
        return redirect(url_for('main.profil'))

    file = request.files['avatar']
    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'error')
        return redirect(url_for('main.profil'))

    if not allowed_file(file.filename):
        flash('Format file tidak didukung. Gunakan PNG, JPG, atau WebP.', 'error')
        return redirect(url_for('main.profil'))

    # Check file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    if file_length > MAX_FILE_SIZE:
        flash('Ukuran file maksimal 2MB.', 'error')
        return redirect(url_for('main.profil'))

    try:
        # Process image with Pillow
        img = Image.open(file.stream)
        img.verify()  # Verify it's a valid image
        file.seek(0)
        img = Image.open(file.stream)

        # Convert to RGB if needed
        img = normalize_image_to_rgb(img)

        # Resize to square (crop center)
        size = min(img.size)
        left = (img.width - size) // 2
        top = (img.height - size) // 2
        img = img.crop((left, top, left + size, top + size))
        img = img.resize((256, 256), Image.Resampling.LANCZOS)

        # Build folder from current_app.root_path (same as payment proofs)
        upload_folder = os.path.join(current_app.root_path, '..', 'static', 'uploads', 'avatars')
        upload_folder = os.path.abspath(upload_folder)
        os.makedirs(upload_folder, exist_ok=True)

        # Generate unique filename
        ext = 'webp'
        filename = f'user_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}'
        filepath = os.path.join(upload_folder, filename)

        # Save as WebP
        img.save(filepath, 'WEBP', quality=85, optimize=True)

        # Delete previous avatar file if inside avatars folder
        old_avatar = current_user.avatar
        if old_avatar:
            old_path = os.path.join(current_app.root_path, '..', old_avatar)
            old_path = os.path.abspath(old_path)
            avatars_dir = upload_folder
            # Only delete if inside avatars folder
            if old_path.startswith(avatars_dir + os.sep) and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

        # Update user avatar
        current_user.avatar = f'uploads/avatars/{filename}'
        db.session.commit()

        flash('Foto profil berhasil diubah.', 'success')
    except Exception:
        flash('Gagal memproses gambar. Pastikan file adalah gambar valid.', 'error')

    return redirect(url_for('main.profil'))


@bp.route('/profil/keamanan')
@login_required
def profil_keamanan():
    """Keamanan tab - Password change"""
    return render_template('profil/keamanan.html')


@bp.route('/profil/password', methods=['POST'])
@login_required
def profil_password():
    current_password = request.form.get('current_password') or ''
    new_password = request.form.get('new_password') or ''
    confirm_password = request.form.get('confirm_password') or ''

    if not current_password or not new_password or not confirm_password:
        flash('Semua field wajib diisi.', 'error')
        return redirect(url_for('main.profil_keamanan'))

    if not current_user.check_password(current_password):
        flash('Password saat ini salah.', 'error')
        return redirect(url_for('main.profil_keamanan'))

    if len(new_password) < 8:
        flash('Password baru minimal 8 karakter.', 'error')
        return redirect(url_for('main.profil_keamanan'))

    if new_password != confirm_password:
        flash('Konfirmasi password tidak cocok.', 'error')
        return redirect(url_for('main.profil_keamanan'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password berhasil diubah.', 'success')
    return redirect(url_for('main.profil_keamanan'))


@bp.route('/profil/riwayat')
@login_required
def profil_riwayat():
    """Riwayat Pesanan tab - Order history"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '').strip()

    valid_statuses = [s for s in Order.VALID_STATUSES]
    if status_filter and status_filter not in valid_statuses:
        status_filter = ''

    query = Order.query.filter_by(user_id=current_user.id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    orders = pagination.items

    return render_template('profil/riwayat.html',
                           orders=orders,
                           pagination=pagination,
                           status_filter=status_filter,
                           valid_statuses=valid_statuses)