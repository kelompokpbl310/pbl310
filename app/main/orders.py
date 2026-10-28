"""Order routes for main blueprint."""

from flask import render_template, url_for, request, redirect, flash, current_app, jsonify
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Product, User, Order, OrderItem, CartItem, Review
from app.security_logging import log_auth_event
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime, timezone
import os
import uuid


@bp.route('/pesanan/<order_code>')
@login_required
def order_detail(order_code):
    """Order detail page"""
    order = Order.query.filter_by(order_code=order_code, user_id=current_user.id).first_or_404()

    # Sync Midtrans status if pending
    if order.status == Order.STATUS_PENDING_PAYMENT and order.midtrans_order_id:
        try:
            from app.payments import sync_midtrans_status
            sync_midtrans_status(order, source='return')
        except Exception as e:
            current_app.logger.warning(f'Midtrans sync on return failed: {e}')

    # Encourage review if order is delivered and has unreviewed products
    if order.status == Order.STATUS_DELIVERED:
        unreviewed = []
        for item in order.items:
            existing = Review.query.filter_by(user_id=current_user.id, product_id=item.product_id).first()
            if not existing:
                unreviewed.append((item.product_id, item.product_name))
        if unreviewed:
            from markupsafe import Markup, escape
            links = []
            for pid, pname in unreviewed:
                url = url_for('main.detail_produk', id=pid) + '#ulasan'
                links.append(f'<a href="{url}" class="font-bold text-maroon underline hover:text-maroon-dark">{escape(pname)}</a>')
            message = Markup(f'Pesanan Anda sudah selesai! Yuk, beri ulasan untuk: {", ".join(links)}.')
            flash(message, 'info')
    
    import os
    client_key = os.getenv('MIDTRANS_CLIENT_KEY', '')
    is_production = os.getenv('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true'
    return render_template('profil/riwayat_detail.html', order=order, client_key=client_key, is_production=is_production)


@bp.route('/pesanan/<order_code>/batal', methods=['POST'])
@login_required
def order_cancel(order_code):
    """Cancel order - only allowed in pending_payment status"""
    order = Order.query.filter_by(order_code=order_code, user_id=current_user.id).first_or_404()

    if not order.can_customer_cancel():
        flash('Pesanan tidak bisa dibatalkan pada status ini.', 'error')
        return redirect(url_for('main.order_detail', order_code=order_code))

    try:
        # If Midtrans transaction exists, cancel it first
        if order.midtrans_order_id:
            try:
                import midtransclient
                import os
                api_client = midtransclient.CoreApi(
                    is_production=os.getenv('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true',
                    server_key=os.getenv('MIDTRANS_SERVER_KEY', ''),
                    client_key=os.getenv('MIDTRANS_CLIENT_KEY', ''),
                )
                api_client.transactions.cancel(order.midtrans_order_id)
            except Exception as e:
                current_app.logger.warning(f'Midtrans cancel failed: {e}')

        # Restore stock for each item
        for item in order.items:
            product = db.session.get(Product, item.product_id)
            if product:
                product.stock += item.quantity

        order.transition_to(Order.STATUS_CANCELLED)
        db.session.commit()

        # Log audit event
        log_auth_event(
            event='order_cancelled',
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            status='success',
            reason=f'Order {order_code} cancelled by customer'
        )

        flash('Pesanan berhasil dibatalkan. Stok telah dikembalikan.', 'success')
    except Exception:
        db.session.rollback()
        log_auth_event(
            event='order_cancelled',
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            status='failure',
            reason=str(Exception)
        )
        flash('Gagal membatalkan pesanan.', 'error')

    return redirect(url_for('main.order_detail', order_code=order_code))


@bp.route('/pesanan/<order_code>/bukti', methods=['POST'])
@login_required
def upload_payment_proof(order_code):
    """Upload payment proof for transfer orders in pending_payment status"""
    order = Order.query.filter_by(order_code=order_code, user_id=current_user.id).first_or_404()

    # Check eligibility
    if not order.can_upload_proof():
        flash('Upload bukti pembayaran tidak diperbolehkan untuk pesanan ini.', 'error')
        return redirect(url_for('main.order_detail', order_code=order_code))

    file = request.files.get('payment_proof')
    if not file or not file.filename:
        flash('File bukti pembayaran wajib diunggah.', 'error')
        return redirect(url_for('main.order_detail', order_code=order_code))

    # Validate file type
    allowed_extensions = {'jpg', 'jpeg', 'png', 'webp', 'pdf'}
    filename = file.filename.lower()
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''

    if ext not in allowed_extensions:
        flash('Format file tidak didukung. Gunakan JPG, PNG, WebP, atau PDF.', 'error')
        return redirect(url_for('main.order_detail', order_code=order_code))

    # Validate file size (5MB max)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > 5 * 1024 * 1024:
        flash('Ukuran file maksimal 5MB.', 'error')
        return redirect(url_for('main.order_detail', order_code=order_code))

    # Validate file content
    try:
        if ext in {'jpg', 'jpeg', 'png', 'webp'}:
            # Verify image with Pillow and re-encode to strip metadata
            from app.main.helpers import normalize_image_to_rgb
            img = Image.open(file.stream)
            img.verify()
            file.seek(0)
            img = Image.open(file.stream)

            # Convert to RGB if needed
            img = normalize_image_to_rgb(img)

            # Re-save to strip metadata
            import io
            output = io.BytesIO()
            img.save(output, format='WEBP', quality=85, optimize=True)
            output.seek(0)
            file_content = output.read()
            file.stream = io.BytesIO(file_content)
            ext = 'webp'
        elif ext == 'pdf':
            # Check PDF signature
            header = file.read(5)
            file.seek(0)
            if header != b'%PDF-':
                flash('File PDF tidak valid.', 'error')
                return redirect(url_for('main.order_detail', order_code=order_code))
    except Exception:
        flash('File tidak valid atau rusak.', 'error')
        return redirect(url_for('main.order_detail', order_code=order_code))

    # Generate random filename
    unique_id = uuid.uuid4().hex[:16]
    new_filename = f'payment_{order_code}_{unique_id}.{ext}'

    # Get upload folder from config or default
    upload_folder = current_app.config.get('PAYMENT_PROOF_UPLOAD_FOLDER',
                                           os.path.join(current_app.root_path, '..', 'uploads', 'payments'))
    upload_folder = os.path.abspath(upload_folder)
    os.makedirs(upload_folder, exist_ok=True)

    # Delete old proof file if exists
    if order.payment_proof:
        old_path = os.path.join(upload_folder, order.payment_proof)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # Save new file
    file_path = os.path.join(upload_folder, new_filename)
    file.save(file_path)

    # Update order
    order.payment_proof = new_filename
    order.payment_uploaded_at = datetime.now(timezone.utc)
    order.transition_to(Order.STATUS_WAITING_VERIFICATION)
    db.session.commit()

    # Log audit event
    log_auth_event(
        event='payment_proof_uploaded',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'Payment proof uploaded for order {order_code}'
    )

    flash('Bukti pembayaran berhasil diunggah. Menunggu verifikasi admin.', 'success')
    return redirect(url_for('main.order_detail', order_code=order_code))


@bp.route('/pesanan/<order_code>/bukti')
@login_required
def view_payment_proof(order_code):
    """Serve payment proof file - only for order owner or admin"""
    from flask import abort, send_from_directory
    order = Order.query.filter_by(order_code=order_code).first_or_404()

    # Check authorization
    if order.user_id != current_user.id and current_user.role != 'admin':
        abort(404)

    if not order.payment_proof:
        abort(404)

    upload_folder = current_app.config.get('PAYMENT_PROOF_UPLOAD_FOLDER',
                                           os.path.join(current_app.root_path, '..', 'uploads', 'payments'))
    upload_folder = os.path.abspath(upload_folder)
    file_path = os.path.join(upload_folder, order.payment_proof)

    if not os.path.exists(file_path):
        abort(404)

    # Determine MIME type
    ext = order.payment_proof.rsplit('.', 1)[-1].lower()
    mimetype_map = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'pdf': 'application/pdf',
    }
    mimetype = mimetype_map.get(ext, 'application/octet-stream')

    return send_from_directory(upload_folder, order.payment_proof, mimetype=mimetype)


@bp.route('/pembayaran/midtrans/notifikasi', methods=['POST'])
def midtrans_notification():
    """Midtrans payment notification webhook."""
    import hashlib
    import hmac
    import os
    import json

    payload = request.get_json(silent=True) or {}
    order_id = payload.get('order_id')
    status_code = payload.get('status_code')
    gross_amount = payload.get('gross_amount')
    signature_key = payload.get('signature_key')

    server_key = os.getenv('MIDTRANS_SERVER_KEY', '')

    # Verify signature
    expected = hashlib.sha512(
        (order_id + status_code + gross_amount + server_key).encode()
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_key or ''):
        log_auth_event(
            event='midtrans_signature_invalid',
            status='failure',
            reason=f'Invalid signature for order {order_id}'
        )
        return jsonify({'status': 'forbidden'}), 403

    # Find order by midtrans_order_id
    order = Order.query.filter_by(midtrans_order_id=order_id).first()
    if not order:
        return jsonify({'status': 'ok'}), 200

    # Compare gross_amount (before sync)
    try:
        if gross_amount is not None and int(float(gross_amount)) != int(order.total_price):
            log_auth_event(
                event='midtrans_amount_mismatch',
                user_id=order.user_id,
                status='failure',
                reason=f'Amount mismatch for order {order.order_code}: {gross_amount} vs {order.total_price}'
            )
            return jsonify({'status': 'ok'}), 200
    except (ValueError, TypeError):
        pass

    from app.payments import sync_midtrans_status
    sync_midtrans_status(order, source='webhook')

    return jsonify({'status': 'ok'}), 200