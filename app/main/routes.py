"""Public page routes for main blueprint."""

from flask import render_template, url_for, abort, request
from datetime import datetime, timezone
from app.main import bp
from app import db
from app.models import Product, MenuType, Review, PromoBanner, Order, OrderItem
from sqlalchemy import func


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

    # Get active menu types for filter
    menu_types = MenuType.query.filter_by(is_active=True).order_by(MenuType.display_order).all()
    from app.models import Category
    categories = Category.query.order_by(Category.name).all()

    # --- Combined customer catalog filters ---
    search = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    menu_type_id = request.args.get('menu_type', type=int)
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    availability = request.args.get('availability', 'all').strip()
    sort = request.args.get('sort', 'newest').strip()

    # Validate prices
    if min_price is not None and min_price < 0:
        min_price = None
    if max_price is not None and max_price < 0:
        max_price = None
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    # Validate sort
    valid_sorts = {'newest', 'name_asc', 'name_desc', 'price_asc', 'price_desc'}
    if sort not in valid_sorts:
        sort = 'newest'

    # Validate availability
    if availability not in ('all', 'in_stock'):
        availability = 'all'

    # Validate category_id
    if category_id:
        cat = Category.query.get(category_id)
        if not cat:
            category_id = None

    # Validate menu_type_id
    if menu_type_id:
        mt = MenuType.query.get(menu_type_id)
        if not mt or not mt.is_active:
            menu_type_id = None

    # Build query
    query = Product.query.filter(Product.is_active == True)

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if menu_type_id:
        query = query.filter(Product.menu_type_id == menu_type_id)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if availability == 'in_stock':
        query = query.filter(Product.stock > 0)

    # Sort
    if sort == 'newest':
        query = query.order_by(Product.created_at.desc(), Product.id.desc())
    elif sort == 'name_asc':
        query = query.order_by(Product.name.asc(), Product.id.asc())
    elif sort == 'name_desc':
        query = query.order_by(Product.name.desc(), Product.id.desc())
    elif sort == 'price_asc':
        query = query.order_by(Product.price.asc(), Product.id.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc(), Product.id.desc())

    products = query.all()

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
            category=p.menu_type.name if p.menu_type else 'Lainnya',
            menu_type_id=p.menu_type_id,
        )

    all_products = [product_to_dict(p) for p in products]

    # --- Popular products based on actual sales ---
    valid_statuses = [Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED]
    popular_query = db.session.query(
        Product,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('total_sold')
    ).join(OrderItem, OrderItem.product_id == Product.id
    ).join(Order, Order.id == OrderItem.order_id
    ).filter(
        Product.is_active == True,
        Order.status.in_(valid_statuses)
    ).group_by(Product.id
    ).order_by(func.sum(OrderItem.quantity).desc(), Product.id.asc()
    ).limit(2).all()

    popular_products = [product_to_dict(p) for p, _ in popular_query]

    # Fallback: fill with featured products if not enough
    if len(popular_products) < 2:
        featured = Product.query.filter_by(is_active=True, is_featured=True).all()
        existing_ids = {p['id'] for p in popular_products}
        for p in featured:
            if p.id not in existing_ids and len(popular_products) < 2:
                popular_products.append(product_to_dict(p))
                existing_ids.add(p.id)

    # Final fallback: newest active products
    if len(popular_products) < 2:
        newest = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
        existing_ids = {p['id'] for p in popular_products}
        for p in newest:
            if p.id not in existing_ids and len(popular_products) < 2:
                popular_products.append(product_to_dict(p))
                existing_ids.add(p.id)

    # Keep featured_products for "Produk Pilihan" section
    featured_products = Product.query.filter_by(is_active=True, is_featured=True).limit(2).all()
    featured_products = [product_to_dict(p) for p in featured_products]

    return render_template('produk.html',
                           promo_slides=slides,
                           menu_types=menu_types,
                           categories=categories,
                           featured_products=featured_products,
                           popular_products=popular_products,
                           all_products=all_products,
                           search=search,
                           category_id=category_id,
                           menu_type_id=menu_type_id,
                           min_price=min_price,
                           max_price=max_price,
                           availability=availability,
                           sort=sort)


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