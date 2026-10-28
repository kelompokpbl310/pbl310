"""Midtrans payment sync utilities."""

import os
import hashlib
import hmac
from datetime import datetime, timezone

from app import db
from app.models import Order, Product
from app.security_logging import log_auth_event


def sync_midtrans_status(order, source='unknown'):
    """Sync order status with Midtrans Get Status API.

    Returns a dict with keys: checked, paid, cancelled, unchanged, error.
    """
    result = {'checked': 0, 'paid': 0, 'cancelled': 0, 'unchanged': 0, 'error': 0}

    if not order.midtrans_order_id:
        result['unchanged'] = 1
        return result

    # Idempotent: already paid or cancelled
    if order.status in (Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED, Order.STATUS_CANCELLED):
        result['unchanged'] = 1
        return result

    if order.status != Order.STATUS_PENDING_PAYMENT:
        result['unchanged'] = 1
        return result

    result['checked'] = 1

    try:
        import midtransclient
        server_key = os.getenv('MIDTRANS_SERVER_KEY', '')
        api_client = midtransclient.CoreApi(
            is_production=os.getenv('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true',
            server_key=server_key,
            client_key=os.getenv('MIDTRANS_CLIENT_KEY', ''),
        )
        status_response = api_client.transactions.status(order.midtrans_order_id)
    except Exception as e:
        result['error'] = 1
        log_auth_event(
            event='midtrans_status_synced',
            user_id=order.user_id,
            status='failure',
            reason=f'source={source} order={order.order_code} error={str(e)}'
        )
        return result

    transaction_status = status_response.get('transaction_status')
    fraud_status = status_response.get('fraud_status')
    payment_type = status_response.get('payment_type')
    transaction_id = status_response.get('transaction_id')
    gross_amount = status_response.get('gross_amount')

    # Compare gross_amount with Order.total_price
    try:
        if gross_amount is not None and int(float(gross_amount)) != int(order.total_price):
            log_auth_event(
                event='midtrans_amount_mismatch',
                user_id=order.user_id,
                status='failure',
                reason=f'source={source} order={order.order_code} amount={gross_amount} vs {order.total_price}'
            )
            result['unchanged'] = 1
            return result
    except (ValueError, TypeError):
        pass

    if transaction_status in ('settlement', 'capture') and (fraud_status in (None, 'accept')):
        # Mark paid
        order.midtrans_transaction_id = transaction_id
        order.midtrans_payment_type = payment_type
        order.paid_at = datetime.now(timezone.utc)
        order.transition_to(Order.STATUS_PAID)
        db.session.commit()
        result['paid'] = 1
        log_auth_event(
            event='midtrans_status_synced',
            user_id=order.user_id,
            status='success',
            reason=f'source={source} order={order.order_code} status=paid'
        )
    elif transaction_status in ('expire', 'cancel', 'deny'):
        # Cancel and restore stock exactly once
        for item in order.items:
            product = db.session.get(Product, item.product_id)
            if product:
                product.stock += item.quantity
        try:
            order.transition_to(Order.STATUS_CANCELLED)
        except ValueError:
            pass
        db.session.commit()
        result['cancelled'] = 1
        log_auth_event(
            event='midtrans_status_synced',
            user_id=order.user_id,
            status='success',
            reason=f'source={source} order={order.order_code} status=cancelled'
        )
    else:
        # pending or unknown: no change
        result['unchanged'] = 1
        log_auth_event(
            event='midtrans_status_synced',
            user_id=order.user_id,
            status='success',
            reason=f'source={source} order={order.order_code} status={transaction_status}'
        )

    return result