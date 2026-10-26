"""Review routes for main blueprint."""

from flask import render_template, url_for, request, redirect, flash
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Product, Review, Order, OrderItem


@bp.route('/produk/<int:product_id>/ulasan', methods=['POST'])
@login_required
def add_review(product_id):
    """Create or update a review for a product.
    Only allowed for customers who have a delivered order containing this product."""
    product = db.session.get(Product, product_id)
    if not product or not product.is_active:
        from flask import abort
        abort(404)

    # Check if user has a delivered order with this product
    has_delivered_order = db.session.query(Order.id).join(OrderItem).filter(
        Order.user_id == current_user.id,
        Order.status == Order.STATUS_DELIVERED,
        OrderItem.product_id == product_id
    ).first()

    if not has_delivered_order:
        flash('Ulasan hanya dapat diberikan setelah pesanan selesai (status: Selesai).', 'error')
        return redirect(url_for('main.detail_produk', id=product_id))

    # Validate rating
    rating = request.form.get('rating', type=int)
    if not rating or not (1 <= rating <= 5):
        flash('Rating harus antara 1 hingga 5.', 'error')
        return redirect(url_for('main.detail_produk', id=product_id))

    # Get comment (optional, max 1000 chars)
    comment = request.form.get('comment', '').strip()
    if comment and len(comment) > 1000:
        flash('Komentar maksimal 1000 karakter.', 'error')
        return redirect(url_for('main.detail_produk', id=product_id))

    # Check if review already exists (unique constraint on user_id, product_id)
    existing_review = Review.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    try:
        if existing_review:
            # Update existing review
            existing_review.rating = rating
            existing_review.comment = comment if comment else None
            db.session.commit()
            flash('Ulasan Anda berhasil diperbarui.', 'success')
        else:
            # Create new review
            review = Review(
                user_id=current_user.id,
                product_id=product_id,
                rating=rating,
                comment=comment if comment else None
            )
            db.session.add(review)
            db.session.commit()
            flash('Terima kasih atas ulasan Anda!', 'success')
    except Exception:
        db.session.rollback()
        flash('Gagal menyimpan ulasan. Silakan coba lagi.', 'error')

    return redirect(url_for('main.detail_produk', id=product_id))


@bp.route('/ulasan/<int:review_id>/hapus', methods=['POST'])
@login_required
def delete_review(review_id):
    """Delete own review only."""
    review = Review.query.filter_by(id=review_id, user_id=current_user.id).first_or_404()
    product_id = review.product_id

    try:
        db.session.delete(review)
        db.session.commit()
        flash('Ulasan berhasil dihapus.', 'success')
    except Exception:
        db.session.rollback()
        flash('Gagal menghapus ulasan.', 'error')

    return redirect(url_for('main.detail_produk', id=product_id))