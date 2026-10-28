"""Checkout routes for main blueprint."""

import os
import re
import secrets
from datetime import date, timedelta

import midtransclient
from flask import render_template, url_for, request, redirect, flash, current_app
from flask_login import login_required, current_user

from app import db
from app.main import bp
from app.main.helpers import build_cart_summary
from app.models import Product, Order, OrderItem, CartItem
from app.security_logging import log_auth_event


ID_MONTHS = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
]


def _get_snap_client():
    """Build a Midtrans Snap client from environment settings."""
    server_key = os.getenv('MIDTRANS_SERVER_KEY', '')
    client_key = os.getenv('MIDTRANS_CLIENT_KEY', '')
    if not server_key or not client_key:
        raise RuntimeError('MIDTRANS_SERVER_KEY or MIDTRANS_CLIENT_KEY is not set')
    return midtransclient.Snap(
        is_production=os.getenv('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true',
        server_key=server_key,
        client_key=client_key,
    )


def _build_item_details(order):
    """Build Midtrans item_details from saved OrderItem snapshots."""
    return [
        {
            'id': str(item.product_id),
            'price': int(item.unit_price),
            'quantity': int(item.quantity),
            'name': item.product_name[:50],
        }
        for item in order.items
    ]


def _request_snap_token(order, phone):
    """Request a Snap token for an order. Raises on failure."""
    item_details = _build_item_details(order)
    gross_amount = int(order.total_price)

    items_total = sum(i['price'] * i['quantity'] for i in item_details)
    if items_total != gross_amount:
        raise ValueError(
            f'Item total {items_total} does not match gross_amount {gross_amount}'
        )

    transaction = {
        'transaction_details': {
            'order_id': order.midtrans_order_id,
            'gross_amount': gross_amount,
        },
        'item_details': item_details,
        'customer_details': {
            'first_name': (current_user.fullname or current_user.username)[:50],
            'email': current_user.email,
            'phone': phone,
        },
    }
    response = _get_snap_client().create_transaction(transaction)
    token = response.get('token')
    if not token:
        raise RuntimeError('Midtrans response did not contain a token')
    return token


@bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items, cart_subtotal, cart_total = build_cart_summary(current_user.id)

    if not cart_items:
        flash('Keranjang Anda kosong. Silakan tambahkan produk terlebih dahulu.', 'warning')
        return redirect(url_for('main.cart'))

    # Quantity must not exceed stock, including out-of-stock products (stock 0)
    exceeded_products = [
        item['name'] for item in cart_items if item['quantity'] > item['stock']
    ]
    if exceeded_products:
        flash(
            f'Stok tidak mencukupi untuk: {", ".join(exceeded_products)}. '
            'Silakan sesuaikan jumlah di keranjang.',
            'error',
        )
        return redirect(url_for('main.cart'))

    if request.method == 'GET':
        return render_template('checkout.html',
                               cart_items=cart_items,
                               cart_subtotal=cart_subtotal,
                               cart_total=cart_total,
                               user=current_user,
                               today=date.today(),
                               timedelta=timedelta)

    # POST - validate form
    recipient_name = request.form.get('recipient_name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    city = request.form.get('city', '').strip()
    delivery_date_str = request.form.get('delivery_date', '').strip()
    delivery_time = request.form.get('delivery_time', '').strip()
    notes = request.form.get('notes', '').strip()
    payment_method = 'midtrans'  # Only payment method for new orders
    delivery_date = None

    errors = {}

    if not recipient_name:
        errors['recipient_name'] = 'Nama penerima wajib diisi.'

    if not phone:
        errors['phone'] = 'Nomor telepon wajib diisi.'
    else:
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
            min_date = date.today() + timedelta(days=1)
            if delivery_date < min_date:
                errors['delivery_date'] = (
                    f'Tanggal pengiriman minimal {min_date.day} '
                    f'{ID_MONTHS[min_date.month - 1]} {min_date.year} (lead time 1 hari).'
                )
        except ValueError:
            errors['delivery_date'] = 'Format tanggal tidak valid.'

    if errors:
        return render_template('checkout.html',
                               cart_items=cart_items,
                               cart_subtotal=cart_subtotal,
                               cart_total=cart_total,
                               user=current_user,
                               errors=errors,
                               form_data=request.form,
                               today=date.today(),
                               timedelta=timedelta), 400

    # Create the order in one transaction
    try:
        product_ids = [item['product_id'] for item in cart_items]
        products = Product.query.filter(Product.id.in_(product_ids)).with_for_update().all()
        product_map = {p.id: p for p in products}

        for item in cart_items:
            product = product_map.get(item['product_id'])
            if not product or not product.is_active:
                raise ValueError(f'Produk {item["name"]} tidak tersedia.')
            if product.stock < item['quantity']:
                raise ValueError(
                    f'Stok {item["name"]} tidak mencukupi (tersedia: {product.stock}).'
                )

        today_str = date.today().strftime('%Y%m%d')
        prefix = f'CB-{today_str}-'
        last_order = (Order.query
                      .filter(Order.order_code.like(f'{prefix}%'))
                      .order_by(Order.id.desc())
                      .first())
        next_num = int(last_order.order_code.split('-')[-1]) + 1 if last_order else 1
        order_code = f'{prefix}{next_num:04d}'

                # Compute the total on the server from locked product prices
        order_total = sum(
            product_map[item['product_id']].price * item['quantity']
            for item in cart_items
        )

        order = Order(
            user_id=current_user.id,
            recipient_name=recipient_name,
            phone=phone,
            address=address,
            city=city,
            delivery_date=delivery_date,
            delivery_time=delivery_time or None,
            notes=notes or None,
            payment_method=payment_method,
            order_code=order_code,
            status=Order.STATUS_PENDING_PAYMENT,
            total_price=order_total,
            midtrans_order_id=f'{order_code}-{secrets.token_hex(4)}'[:50],
        )
        db.session.add(order)
        db.session.flush()

        for item in cart_items:
            product = product_map[item['product_id']]
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,   # Snapshot
                unit_price=product.price,    # Snapshot
                quantity=item['quantity'],
                subtotal=product.price * item['quantity'],
            ))
            product.stock -= item['quantity']

        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('main.cart'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Checkout failed')
        log_auth_event(
            event='order_created',
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            status='failure',
            reason=type(e).__name__,
        )
        flash('Terjadi kesalahan saat memproses pesanan. Silakan coba lagi.', 'error')
        return redirect(url_for('main.cart'))

    log_auth_event(
        event='order_created',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'Order {order.order_code} created, total={order.total_price}, '
               f'midtrans={order.midtrans_order_id}',
    )

    # The order is saved. A Snap token failure must not undo it.
    try:
        order.snap_token = _request_snap_token(order, phone)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Midtrans snap token error for order %s', order.order_code
        )
        flash('Pesanan dibuat, tetapi pembayaran belum siap. '
              'Silakan coba lagi dari halaman pesanan.', 'warning')
        return redirect(url_for('main.order_detail', order_code=order.order_code))

    flash('Pesanan berhasil dibuat! Silakan lanjutkan pembayaran.', 'success')
    return redirect(url_for('main.order_detail', order_code=order.order_code))
