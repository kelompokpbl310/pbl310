"""Cart routes for main blueprint."""

from flask import render_template, url_for, request, redirect, flash, jsonify
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Product, CartItem
from app.main.helpers import build_cart_summary


@bp.route('/keranjang')
@login_required
def cart():
    """Display cart page with items from database."""
    cart_items, cart_subtotal, cart_total = build_cart_summary(current_user.id)

    return render_template('cart.html',
                           cart_items=cart_items,
                           cart_subtotal=cart_subtotal,
                           cart_total=cart_total)


@bp.route('/keranjang/tambah', methods=['POST'])
@login_required
def cart_add():
    """Add product to cart (from detail page or product listing). POST only."""
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)

    if not product_id:
        flash('Produk tidak valid.', 'error')
        return redirect(request.referrer or url_for('main.produk'))

    product = db.session.get(Product, product_id)
    if not product or not product.is_active:
        flash('Produk tidak ditemukan.', 'error')
        return redirect(request.referrer or url_for('main.produk'))

    # Stock 0 means not purchasable
    if product.stock <= 0:
        flash('Produk ini sedang habis stok.', 'error')
        return redirect(request.referrer or url_for('main.detail_produk', id=product_id))

    if quantity > product.stock:
        flash(f'Stok tersedia hanya {product.stock}.', 'error')
        return redirect(request.referrer or url_for('main.detail_produk', id=product_id))

    # Find or create CartItem for current user
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    if cart_item:
        new_qty = cart_item.quantity + quantity
        cart_item.quantity = min(new_qty, product.stock)
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=product_id,
            quantity=min(quantity, product.stock)
        )
        db.session.add(cart_item)

    db.session.commit()

    flash(f'{product.name} ditambahkan ke keranjang.', 'success')
    return redirect(url_for('main.cart'))


@bp.route('/keranjang/update', methods=['POST'])
@login_required
def cart_update():
    """Update cart quantities, remove items, or clear cart."""
    is_autosave = request.form.get('update') == '1'

    # Explicit clear action (clear button)
    if request.form.get('clear') == '1':
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash('Keranjang dikosongkan.', 'success')
        if is_autosave:
            return jsonify(ok=True, cart_count=0, cart_subtotal=0, cart_total=0)
        return redirect(url_for('main.cart'))

    # Explicit remove action (trash button)
    remove_id = request.form.get('remove')
    if remove_id:
        try:
            product_id = int(remove_id)
            cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if cart_item:
                name = cart_item.product.name if cart_item.product else 'Produk'
                db.session.delete(cart_item)
                db.session.commit()
                flash(f'{name} dihapus dari keranjang.', 'success')
        except (ValueError, TypeError):
            pass
        if is_autosave:
            cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
            return jsonify(ok=True, cart_count=cart_count)
        return redirect(url_for('main.cart'))

    # Normal quantity update (autosave or explicit form submit)
    updated = False
    for key, qty_str in request.form.items():
        if key.startswith('quantities[') and key.endswith(']'):
            try:
                pid = int(key[11:-1])  # Extract product_id from 'quantities[ID]'
                qty = int(qty_str)
                if qty > 0:
                    product = db.session.get(Product, pid)
                    if product:
                        max_qty = product.stock if product.stock > 0 else 0
                        if max_qty <= 0:
                            continue
                        qty = min(qty, max_qty)
                        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
                        if cart_item:
                            cart_item.quantity = qty
                            updated = True
            except (ValueError, TypeError):
                pass

    if updated:
        db.session.commit()
        # Only flash for explicit form submissions, not autosave
        if not is_autosave:
            flash('Keranjang diperbarui.', 'success')

    # Recalculate totals for response
    cart_items_db = CartItem.query.filter_by(user_id=current_user.id).join(Product).all()
    cart_count = len(cart_items_db)
    cart_subtotal = sum(item.quantity * item.product.price for item in cart_items_db)
    cart_total = cart_subtotal  # shipping is free

    if is_autosave:
        return jsonify(ok=True, cart_count=cart_count, cart_subtotal=cart_subtotal, cart_total=cart_total)

    return redirect(url_for('main.cart'))


@bp.route('/keranjang/hapus/<int:product_id>', methods=['POST'])
@login_required
def cart_remove(product_id):
    """Remove single item from cart."""
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    if cart_item:
        name = cart_item.product.name if cart_item.product else 'Produk'
        db.session.delete(cart_item)
        db.session.commit()
        flash(f'{name} dihapus dari keranjang.', 'success')

    return redirect(url_for('main.cart'))