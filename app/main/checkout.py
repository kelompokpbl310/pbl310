"""Checkout routes for main blueprint."""

from flask import render_template, url_for, request, redirect, flash
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Product, Order, OrderItem, CartItem
from app.security_logging import log_auth_event
from datetime import date, datetime, timedelta
from app.main.helpers import build_cart_summary
import re


ID_MONTHS = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
]


@bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items, cart_subtotal, cart_total = build_cart_summary(current_user.id)

    if not cart_items:
        flash('Keranjang Anda kosong. Silakan tambahkan produk terlebih dahulu.', 'warning')
        return redirect(url_for('main.cart'))

    # Check if any cart quantity exceeds current stock
    exceeded_products = []
    for item in cart_items:
        if item['quantity'] > item['stock'] and item['stock'] > 0:
            exceeded_products.append(item['name'])

    if exceeded_products:
        flash(f'Stok tidak mencukupi untuk: {", ".join(exceeded_products)}. Silakan sesuaikan jumlah di keranjang.', 'error')
        return redirect(url_for('main.cart'))

    if request.method == 'GET':
        # Prefill from current_user
        return render_template('checkout.html',
                               cart_items=cart_items,
                               cart_subtotal=cart_subtotal,
                               cart_total=cart_total,
                               user=current_user,
                               today=date.today(),
                               timedelta=timedelta)

    # POST - Process checkout
    # Validate required fields
    recipient_name = request.form.get('recipient_name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    city = request.form.get('city', '').strip()
    delivery_date_str = request.form.get('delivery_date', '').strip()
    delivery_time = request.form.get('delivery_time', '').strip()
    notes = request.form.get('notes', '').strip()
    payment_method = request.form.get('payment_method', '').strip()

    errors = {}

    if not recipient_name:
        errors['recipient_name'] = 'Nama penerima wajib diisi.'

    # Phone validation: Indonesian format, digits only after normalizing, 10-15 digits
    if not phone:
        errors['phone'] = 'Nomor telepon wajib diisi.'
    else:
        # Normalize: remove spaces, dashes, parentheses, plus sign
        phone_normalized = re.sub(r'[\s\-\(\)\+]', '', phone)
        if not phone_normalized.isdigit() or not (10 <= len(phone_normalized) <= 15):
            errors['phone'] = 'Format nomor telepon tidak valid (10-15 digit).'
        else:
            phone = phone_normalized

    if not address:
        errors['address'] = 'Alamat lengkap wajib diisi.'

    if not city:
        errors['city'] = 'Kota wajib diisi.'

    if not delivery_date_str:
        errors['delivery_date'] = 'Tanggal pengiriman wajib diisi.'
    else:
        try:
            delivery_date = date.fromisoformat(delivery_date_str)
            # Minimum lead time: 1 day (tomorrow or later)
            min_date = date.today() + timedelta(days=1)
            if delivery_date < min_date:
                errors['delivery_date'] = f'Tanggal pengiriman minimal {min_date.day} {ID_MONTHS[min_date.month - 1]} {min_date.year} (lead time 1 hari).'
        except ValueError:
            errors['delivery_date'] = 'Format tanggal tidak valid.'

    if payment_method not in ('transfer', 'cod'):
        errors['payment_method'] = 'Metode pembayaran tidak valid.'

    if errors:
        # Re-render with errors and entered values
        return render_template('checkout.html',
                               cart_items=cart_items,
                               cart_subtotal=cart_subtotal,
                               cart_total=cart_total,
                               user=current_user,
                               errors=errors,
                               form_data=request.form,
                               today=date.today(),
                               timedelta=timedelta), 400

    # All validation passed - create order in transaction
    try:
        # Lock product rows to prevent overselling
        product_ids = [item['product_id'] for item in cart_items]
        products = Product.query.filter(Product.id.in_(product_ids)).with_for_update().all()
        product_map = {p.id: p for p in products}

        # Re-check stock and active status
        for item in cart_items:
            product = product_map.get(item['product_id'])
            if not product or not product.is_active:
                raise ValueError(f'Produk {item["name"]} tidak tersedia.')
            if product.stock < item['quantity']:
                raise ValueError(f'Stok {item["name"]} tidak mencukupi (tersedia: {product.stock}).')

        # Generate unique order_code: CB-YYYYMMDD-NNNN
        today_str = date.today().strftime('%Y%m%d')
        prefix = f'CB-{today_str}-'
        last_order = Order.query.filter(Order.order_code.like(f'{prefix}%')).order_by(Order.id.desc()).first()
        if last_order:
            last_num = int(last_order.order_code.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        order_code = f'{prefix}{next_num:04d}'

        # Determine initial status
        initial_status = Order.STATUS_PROCESSING if payment_method == 'cod' else Order.STATUS_PENDING_PAYMENT

        # Create Order
        order = Order(
            user_id=current_user.id,
            recipient_name=recipient_name,
            phone=phone,
            address=address,
            city=city,
            delivery_date=delivery_date,
            delivery_time=delivery_time if delivery_time else None,
            notes=notes if notes else None,
            payment_method=payment_method,
            order_code=order_code,
            status=initial_status,
            total_price=cart_total,
        )
        db.session.add(order)
        db.session.flush()  # Get order.id

        # Create OrderItems and decrease stock
        for item in cart_items:
            product = product_map[item['product_id']]
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,  # Snapshot
                unit_price=product.price,    # Snapshot
                quantity=item['quantity'],
                subtotal=item['subtotal'],
            )
            db.session.add(order_item)
            product.stock -= item['quantity']

        # Clear cart
        CartItem.query.filter_by(user_id=current_user.id).delete()

        db.session.commit()

        # Log audit event
        log_auth_event(
            event='order_created',
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            status='success',
            reason=f'Order {order_code} created, total={cart_total}'
        )

        flash('Pesanan berhasil dibuat!', 'success')
        return redirect(url_for('main.order_detail', order_code=order_code))

    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('main.cart'))
    except Exception as e:
        db.session.rollback()
        # Log audit event for failure
        log_auth_event(
            event='order_created',
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            status='failure',
            reason=str(e)
        )
        flash('Terjadi kesalahan saat memproses pesanan. Silakan coba lagi.', 'error')
        return redirect(url_for('main.cart'))