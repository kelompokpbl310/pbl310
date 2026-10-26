"""Public page routes for main blueprint."""

from flask import render_template, url_for, abort
from datetime import datetime, timezone
from app.main import bp
from app import db
from app.models import Product, MenuType, Review, PromoBanner


@bp.route('/')
def index():
    # Get active menu types for "Paket Pilihan" section
    menu_types = MenuType.query.filter_by(is_active=True).order_by(MenuType.display_order).all()

    # Get featured products for "Paket Pilihan" (fallback to first active product per menu type)
    paket_pilihan = []
    for mt in menu_types:
        product = Product.query.filter_by(is_active=True, menu_type_id=mt.id).first()
        if product:
            paket_pilihan.append(product)

    return render_template('index.html', menu_types=menu_types, paket_pilihan=paket_pilihan)


@bp.route('/produk')
def produk():
    # Query active promo banners within date window
    now = datetime.now(timezone.utc)
    promo_banners = PromoBanner.query.filter(
        PromoBanner.is_active == True,
        (PromoBanner.starts_at == None) | (PromoBanner.starts_at <= now),
        (PromoBanner.ends_at == None) | (PromoBanner.ends_at >= now)
    ).order_by(PromoBanner.display_order, PromoBanner.id).all()

    slides = []
    for b in promo_banners:
        # Build CTA link on the server
        if b.product_id and b.product and b.product.is_active:
            cta_url = url_for('main.detail_produk', id=b.product_id)
        elif b.cta_url:
            cta_url = b.cta_url
        else:
            cta_url = url_for('main.produk')

        slides.append({
            'badge': b.badge,
            'headline': b.headline,
            'subtitle': b.subtitle,
            'price': b.price,
            'unit': b.unit,
            'cta_label': b.cta_label,
            'cta_url': cta_url,
            'image': b.image,
            'alt_text': b.alt_text,
        })

    # Get active menu types for filter tabs
    menu_types = MenuType.query.filter_by(is_active=True).order_by(MenuType.display_order).all()

    # Get active products from DB
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()

    # Get featured products for "Produk Populer"
    featured_products = Product.query.filter_by(is_active=True, is_featured=True).limit(2).all()

    # Compute average ratings for all products in one query
    from sqlalchemy import func
    avg_ratings = db.session.query(
        Review.product_id,
        func.avg(Review.rating).label('avg_rating'),
        func.count(Review.id).label('review_count')
    ).group_by(Review.product_id).all()
    avg_rating_map = {r.product_id: (float(r.avg_rating), r.review_count) for r in avg_ratings}

    # Convert DB products to dict format for template compatibility
    def product_to_dict(p):
        avg_rating, review_count = avg_rating_map.get(p.id, (0, 0))
        return dict(
            id=p.id,
            name=p.name,
            desc=p.description or '',
            price=p.price,
            unit='1 porsi' if p.stock > 0 else 'Habis',
            stock=p.stock,
            rating=avg_rating,
            reviews=review_count,
            img=p.image.replace('static/', '') if p.image else 'img/assets1.png',
            category=p.menu_type.name if p.menu_type else 'Lainnya'
        )

    featured_products = [product_to_dict(p) for p in featured_products]
    all_products = [product_to_dict(p) for p in products]
    # Sort: in-stock products first, out-of-stock at the end
    all_products.sort(key=lambda p: 0 if p['stock'] > 0 else 1)

    return render_template('produk.html',
                           promo_slides=slides,
                           menu_types=menu_types,
                           featured_products=featured_products,
                           all_products=all_products)


@bp.route('/detail-produk/<int:id>')
def detail_produk(id):
    product = db.session.get(Product, id)
    if not product or not product.is_active:
        from flask import abort
        abort(404)

    # Get related products (same menu type, excluding current)
    related_products = Product.query.filter(
        Product.menu_type_id == product.menu_type_id,
        Product.is_active == True,
        Product.id != product.id
    ).limit(4).all()

    # Get reviews for this product
    reviews = Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).all()

    # Calculate average rating
    avg_rating = 0
    if reviews:
        avg_rating = sum(r.rating for r in reviews) / len(reviews)

    return render_template('detail-produk.html',
                           product=product,
                           related_products=related_products,
                           reviews=reviews,
                           avg_rating=avg_rating)


@bp.route('/tentang')
def tentang():
    return render_template('tentang.html')