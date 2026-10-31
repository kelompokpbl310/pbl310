"""Admin Routes - Dashboard & Management"""

from functools import wraps
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Category, Product, PromoBanner, Order, OrderItem, User, MenuType
from app.admin import bp
from app.security_logging import log_auth_event
from werkzeug.utils import secure_filename
from PIL import Image
import os
import uuid
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone


# Image upload constants
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
UPLOAD_FOLDER = 'static/uploads/products'
PROMO_UPLOAD_FOLDER = 'static/uploads/promo'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file, folder, prefix='item'):
    """Process and save image as WebP, return relative path or None."""
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        raise ValueError('Format file tidak didukung. Gunakan PNG, JPG, atau WebP.')

    # Check file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    if file_length > MAX_FILE_SIZE:
        raise ValueError('Ukuran file maksimal 2MB.')

    try:
        # Process image with Pillow
        img = Image.open(file.stream)
        img.verify()
        file.seek(0)
        img = Image.open(file.stream)

        # Convert to RGB if needed (for WebP)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize to max 800px on longest side, maintain aspect ratio
        max_dim = 800
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        # Generate unique filename
        ext = 'webp'
        unique_id = uuid.uuid4().hex[:8]
        filename = f'{prefix}_{unique_id}.{ext}'
        filepath = os.path.join(current_app.root_path, folder, filename)

        # Ensure upload directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Save as WebP
        img.save(filepath, 'WEBP', quality=85, optimize=True)

        return f'{folder}/{filename}'
    except Exception as e:
        raise ValueError('Gagal memproses gambar. Pastikan file adalah gambar valid.')


def save_product_image(file, product_id=None):
    """Process and save product image as WebP, return relative path or None."""
    return save_image(file, UPLOAD_FOLDER, f'product_{product_id}' if product_id else 'product_new')


def save_promo_image(file, banner_id=None):
    """Process and save promo banner image as WebP, return relative path or None."""
    return save_image(file, PROMO_UPLOAD_FOLDER, f'promo_{banner_id}' if banner_id else 'promo_new')


def validate_cta_url(url):
    """Validate cta_url - allow only relative paths starting with / or http/https URLs."""
    if not url:
        return True, None
    parsed = urlparse(url)
    if parsed.scheme in ('', 'http', 'https'):
        if parsed.scheme == '' and not url.startswith('/'):
            return False, 'URL relatif harus dimulai dengan "/"'
        return True, None
    return False, 'Skema URL tidak diizinkan. Gunakan URL relatif (awali dengan "/") atau https://'


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
    """Dashboard with real-time statistics."""
    from sqlalchemy import func
    from datetime import date, timedelta

    # Today's date
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    today_str = today.strftime('%Y-%m-%d')

    # Orders waiting verification
    waiting_verification_count = Order.query.filter_by(status=Order.STATUS_WAITING_VERIFICATION).count()

    # Orders in process (processing)
    processing_count = Order.query.filter_by(status=Order.STATUS_PROCESSING).count()

    # Today's revenue from paid/processing/delivered orders
    today_revenue = db.session.query(func.sum(Order.total_price)).filter(
        func.date(Order.created_at) == today,
        Order.status.in_([Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED])
    ).scalar() or 0

    # This week's revenue
    week_revenue = db.session.query(func.sum(Order.total_price)).filter(
        func.date(Order.created_at) >= week_ago,
        Order.status.in_([Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED])
    ).scalar() or 0

    # Previous week's revenue for comparison
    prev_week_start = week_ago - timedelta(days=7)
    prev_week_revenue = db.session.query(func.sum(Order.total_price)).filter(
        func.date(Order.created_at) >= prev_week_start,
        func.date(Order.created_at) < week_ago,
        Order.status.in_([Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED])
    ).scalar() or 0

    # Total active orders (not delivered, not cancelled)
    active_orders_count = Order.query.filter(
        Order.status.notin_([Order.STATUS_DELIVERED, Order.STATUS_CANCELLED])
    ).count()

    # Total customers
    total_customers = User.query.filter_by(role='customer').count()

    # New customers this month
    new_customers_month = User.query.filter(
        User.role == 'customer',
        func.date(User.created_at) >= month_ago
    ).count()

    # Recent orders (last 5)
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    # Best-selling products this week
    from sqlalchemy import func
    best_products = db.session.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label('total_qty'),
    ).join(Order).filter(
        Order.status.in_([Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED]),
        func.date(Order.created_at) >= week_ago,
    ).group_by(OrderItem.product_name).order_by(func.sum(OrderItem.quantity).desc()).limit(3).all()

    # Week-over-week change percentage
    if prev_week_revenue > 0:
        wow_change = ((week_revenue - prev_week_revenue) / prev_week_revenue) * 100
    else:
        wow_change = 100 if week_revenue > 0 else 0

    return render_template('dashboard/ringkasan.html',
        waiting_verification_count=waiting_verification_count,
        processing_count=processing_count,
        today_revenue=today_revenue,
        week_revenue=week_revenue,
        wow_change=round(wow_change, 1),
        active_orders_count=active_orders_count,
        total_customers=total_customers,
        new_customers_month=new_customers_month,
        recent_orders=recent_orders,
        best_products=best_products,
        today_date=today_str,
    )


@bp.route('/pesanan')
@login_required
@admin_required
def pesanan():
    """List orders with filtering, search, and pagination."""
    from sqlalchemy import or_, func
    from datetime import datetime, date

    # Query parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('q', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    # Base query with joins
    query = Order.query.join(User, Order.user_id == User.id)

    # Status filter - map Indonesian labels to status constants
    status_map = {
        'pending_payment': Order.STATUS_PENDING_PAYMENT,
        'waiting_verification': Order.STATUS_WAITING_VERIFICATION,
        'paid': Order.STATUS_PAID,
        'processing': Order.STATUS_PROCESSING,
        'delivered': Order.STATUS_DELIVERED,
        'cancelled': Order.STATUS_CANCELLED,
    }

    # Also map Indonesian display labels
    status_display_map = {
        'menunggu pembayaran': Order.STATUS_PENDING_PAYMENT,
        'menunggu verifikasi': Order.STATUS_WAITING_VERIFICATION,
        'dibayar': Order.STATUS_PAID,
        'diproses': Order.STATUS_PROCESSING,
        'selesai': Order.STATUS_DELIVERED,
        'dibatalkan': Order.STATUS_CANCELLED,
    }

    if status_filter:
        # Try exact match first, then case-insensitive display label match
        status_key = status_filter.lower().replace(' ', '_')
        if status_key in status_map:
            query = query.filter(Order.status == status_map[status_key])
        elif status_filter.lower() in status_display_map:
            query = query.filter(Order.status == status_display_map[status_filter.lower()])

    # Search by order_code or customer name
    if search:
        query = query.filter(
            or_(
                Order.order_code.ilike(f'%{search}%'),
                User.fullname.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
            )
        )

    # Date range filter
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(func.date(Order.created_at) >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(func.date(Order.created_at) <= dt_to)
        except ValueError:
            pass

    # Order by created_at desc
    query = query.order_by(Order.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    orders = pagination.items

    # Summary counts for dashboard
    waiting_verification_count = Order.query.filter_by(status=Order.STATUS_WAITING_VERIFICATION).count()
    processing_count = Order.query.filter_by(status=Order.STATUS_PROCESSING).count()
    # Today's revenue from paid/processing/delivered orders
    today = date.today()
    today_revenue = db.session.query(func.sum(Order.total_price)).filter(
        func.date(Order.created_at) == today,
        Order.status.in_([Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED])
    ).scalar() or 0

    return render_template('dashboard/pesanan.html',
        orders=orders,
        pagination=pagination,
        status_filter=status_filter,
        search=search,
        date_from=date_from,
        date_to=date_to,
        waiting_verification_count=waiting_verification_count,
        processing_count=processing_count,
        today_revenue=today_revenue,
    )


@bp.route('/pesanan/<order_code>')
@login_required
@admin_required
def pesanan_detail(order_code):
    """Admin order detail view."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()
    return render_template('dashboard/pesanan_detail.html', order=order)


@bp.route('/pesanan/<order_code>/approve', methods=['POST'])
@login_required
@admin_required
def pesanan_approve(order_code):
    """Approve payment proof: waiting_verification -> paid."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()

    if not order.can_transition_to(Order.STATUS_PAID):
        flash('Tidak bisa menyetujui pesanan ini. Status tidak valid untuk transisi.', 'error')
        return redirect(url_for('admin.pesanan_detail', order_code=order_code))

    old_status = order.status
    order.transition_to(Order.STATUS_PAID)
    # Clear rejection reason on approval
    order.rejection_reason = None
    db.session.commit()

    # Audit log
    log_auth_event(
        event='payment_approved',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'Order {order_code} approved: {old_status} -> {Order.STATUS_PAID}'
    )

    flash('Pembayaran disetujui. Status pesanan menjadi Dibayar.', 'success')
    return redirect(url_for('admin.pesanan_detail', order_code=order_code))


@bp.route('/pesanan/<order_code>/reject', methods=['POST'])
@login_required
@admin_required
def pesanan_reject(order_code):
    """Reject payment proof: waiting_verification -> pending_payment with reason."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()

    if not order.can_transition_to(Order.STATUS_PENDING_PAYMENT):
        flash('Tidak bisa menolak pesanan ini. Status tidak valid untuk transisi.', 'error')
        return redirect(url_for('admin.pesanan_detail', order_code=order_code))

    reason = request.form.get('rejection_reason', '').strip()
    if not reason:
        flash('Alasan penolakan wajib diisi.', 'error')
        return redirect(url_for('admin.pesanan_detail', order_code=order_code))

    old_status = order.status
    order.transition_to(Order.STATUS_PENDING_PAYMENT)
    order.rejection_reason = reason
    # Keep payment_proof file but customer can re-upload
    order.payment_uploaded_at = None
    db.session.commit()

    # Audit log
    log_auth_event(
        event='payment_rejected',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'Order {order_code} rejected: {old_status} -> {Order.STATUS_PENDING_PAYMENT}. Reason: {reason}'
    )

    flash('Pembayaran ditolak. Pelanggan dapat mengunggah bukti baru.', 'success')
    return redirect(url_for('admin.pesanan_detail', order_code=order_code))


@bp.route('/pesanan/<order_code>/cek-midtrans', methods=['POST'])
@login_required
@admin_required
def pesanan_check_midtrans(order_code):
    """Check Midtrans status for an order."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()
    if not order.midtrans_order_id:
        flash('Tidak ada transaksi Midtrans untuk pesanan ini.', 'warning')
        return redirect(url_for('admin.pesanan_detail', order_code=order_code))

    try:
        from app.payments import sync_midtrans_status
        result = sync_midtrans_status(order, source='admin')
        # Refresh order from DB
        db.session.refresh(order)
        flash(f'Status Midtrans disinkronkan. Status: {order.status}', 'info')
    except Exception as e:
        flash(f'Gagal mengecek status Midtrans: {str(e)}', 'error')

    return redirect(url_for('admin.pesanan_detail', order_code=order_code))


@bp.route('/pesanan/<order_code>/process', methods=['POST'])
@login_required
@admin_required
def pesanan_process(order_code):
    """Process order: paid -> processing."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()

    if not order.can_transition_to(Order.STATUS_PROCESSING):
        flash('Tidak bisa memproses pesanan ini. Status tidak valid untuk transisi.', 'error')
        return redirect(url_for('admin.pesanan_detail', order_code=order_code))

    old_status = order.status
    order.transition_to(Order.STATUS_PROCESSING)
    db.session.commit()

    # Audit log
    log_auth_event(
        event='order_status_changed',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'Order {order_code} status changed: {old_status} -> {Order.STATUS_PROCESSING}'
    )

    flash('Pesanan diproses.', 'success')
    return redirect(url_for('admin.pesanan_detail', order_code=order_code))


@bp.route('/pesanan/<order_code>/complete', methods=['POST'])
@login_required
@admin_required
def pesanan_complete(order_code):
    """Complete order: processing -> delivered."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()

    if not order.can_transition_to(Order.STATUS_DELIVERED):
        flash('Tidak bisa menyelesaikan pesanan ini. Status tidak valid untuk transisi.', 'error')
        return redirect(url_for('admin.pesanan_detail', order_code=order_code))

    old_status = order.status
    order.transition_to(Order.STATUS_DELIVERED)
    db.session.commit()

    # Audit log
    log_auth_event(
        event='order_status_changed',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'Order {order_code} status changed: {old_status} -> {Order.STATUS_DELIVERED}'
    )

    flash('Pesanan selesai.', 'success')
    return redirect(url_for('admin.pesanan_detail', order_code=order_code))


@bp.route('/pesanan/<order_code>/cancel', methods=['POST'])
@login_required
@admin_required
def pesanan_cancel(order_code):
    """Admin cancel order: restore stock if before delivered."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()

    # Admin can cancel only before delivered
    if order.status in [Order.STATUS_DELIVERED, Order.STATUS_CANCELLED]:
        flash('Tidak bisa membatalkan pesanan yang sudah selesai atau dibatalkan.', 'error')
        return redirect(url_for('admin.pesanan_detail', order_code=order_code))

    old_status = order.status

    # Restore stock for each item
    for item in order.items:
        product = db.session.get(Product, item.product_id)
        if product:
            product.stock += item.quantity

    order.transition_to(Order.STATUS_CANCELLED)
    db.session.commit()

    # Audit log
    log_auth_event(
        event='order_status_changed',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'Order {order_code} cancelled by admin: {old_status} -> {Order.STATUS_CANCELLED}. Stock restored.'
    )

    flash('Pesanan dibatalkan. Stok dikembalikan.', 'success')
    return redirect(url_for('admin.pesanan_detail', order_code=order_code))


@bp.route('/produk')
@login_required
@admin_required
def produk():
    categories = Category.query.order_by(Category.name).all()
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('dashboard/produk.html', categories=categories, products=products)


# --- Kategori CRUD ---
@bp.route('/kategori')
@login_required
@admin_required
def kategori():
    categories = Category.query.order_by(Category.name).all()
    menu_types = MenuType.query.order_by(MenuType.display_order, MenuType.name).all()
    return render_template('dashboard/kategori.html', categories=categories, menu_types=menu_types)


@bp.route('/kategori/create', methods=['GET', 'POST'])
@login_required
@admin_required
def kategori_create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if not name:
            flash('Nama kategori wajib diisi.', 'error')
        else:
            slug = name.lower().replace(' ', '-')
            existing = Category.query.filter_by(slug=slug).first()
            if existing:
                flash('Kategori dengan nama serupa sudah ada.', 'error')
            else:
                cat = Category(name=name, slug=slug, description=description)
                db.session.add(cat)
                db.session.commit()
                flash('Kategori berhasil ditambahkan.', 'success')
                return redirect(url_for('admin.kategori'))
    return render_template('dashboard/kategori_form.html', category=None)


@bp.route('/kategori/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def kategori_edit(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if not name:
            flash('Nama kategori wajib diisi.', 'error')
        else:
            slug = name.lower().replace(' ', '-')
            existing = Category.query.filter(Category.slug == slug, Category.id != id).first()
            if existing:
                flash('Kategori dengan nama serupa sudah ada.', 'error')
            else:
                category.name = name
                category.slug = slug
                category.description = description
                db.session.commit()
                flash('Kategori berhasil diperbarui.', 'success')
                return redirect(url_for('admin.kategori'))
    return render_template('dashboard/kategori_form.html', category=category)


@bp.route('/kategori/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def kategori_delete(id):
    category = Category.query.get_or_404(id)
    if category.products:
        flash('Kategori tidak bisa dihapus karena masih memiliki produk.', 'error')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Kategori berhasil dihapus.', 'success')
    return redirect(url_for('admin.kategori'))


# --- MenuType CRUD ---
@bp.route('/menu-type/create', methods=['GET', 'POST'])
@login_required
@admin_required
def menu_type_create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        display_order = request.form.get('display_order', type=int) or 0
        if not name:
            flash('Nama tipe menu wajib diisi.', 'error')
        else:
            slug = name.lower().replace(' ', '-')
            existing = MenuType.query.filter_by(slug=slug).first()
            if existing:
                flash('Tipe menu dengan nama serupa sudah ada.', 'error')
            else:
                mt = MenuType(name=name, slug=slug, description=description, display_order=display_order, is_active=True)
                db.session.add(mt)
                db.session.commit()
                flash('Tipe menu berhasil ditambahkan.', 'success')
                return redirect(url_for('admin.kategori'))
    return render_template('dashboard/menu_type_form.html', menu_type=None)


@bp.route('/menu-type/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def menu_type_edit(id):
    mt = MenuType.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        display_order = request.form.get('display_order', type=int) or 0
        is_active = bool(request.form.get('is_active'))
        if not name:
            flash('Nama tipe menu wajib diisi.', 'error')
        else:
            slug = name.lower().replace(' ', '-')
            existing = MenuType.query.filter(MenuType.slug == slug, MenuType.id != id).first()
            if existing:
                flash('Tipe menu dengan nama serupa sudah ada.', 'error')
            else:
                mt.name = name
                mt.slug = slug
                mt.description = description
                mt.display_order = display_order
                mt.is_active = is_active
                db.session.commit()
                flash('Tipe menu berhasil diperbarui.', 'success')
                return redirect(url_for('admin.kategori'))
    return render_template('dashboard/menu_type_form.html', menu_type=mt)


@bp.route('/menu-type/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def menu_type_delete(id):
    mt = MenuType.query.get_or_404(id)
    if mt.products:
        flash('Tipe menu tidak bisa dihapus karena masih memiliki produk.', 'error')
    else:
        db.session.delete(mt)
        db.session.commit()
        flash('Tipe menu berhasil dihapus.', 'success')
    return redirect(url_for('admin.kategori'))


@bp.route('/menu-type/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def menu_type_toggle(id):
    mt = MenuType.query.get_or_404(id)
    mt.is_active = not mt.is_active
    db.session.commit()
    flash(f'Tipe menu {"diaktifkan" if mt.is_active else "dinonaktifkan"}.', 'success')
    return redirect(url_for('admin.kategori'))


# --- Produk CRUD ---
@bp.route('/produk/create', methods=['GET', 'POST'])
@login_required
@admin_required
def produk_create():
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        description = request.form.get('description', '').strip()
        price = request.form.get('price', type=int)
        stock = request.form.get('stock', type=int)
        image = request.files.get('image')

        errors = []
        if not name:
            errors.append('Nama produk wajib diisi.')
        if not category_id:
            errors.append('Kategori wajib dipilih.')
        if price is None or price < 0:
            errors.append('Harga tidak valid.')
        if stock is None or stock < 0:
            errors.append('Stok tidak valid.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            slug = name.lower().replace(' ', '-')
            existing = Product.query.filter_by(slug=slug).first()
            if existing:
                flash('Produk dengan nama serupa sudah ada.', 'error')
            else:
                # Create product first to get ID for image filename
                prod = Product(
                    category_id=category_id,
                    name=name,
                    slug=slug,
                    description=description,
                    price=price,
                    stock=stock,
                    is_active=True,
                    is_featured=bool(request.form.get('is_featured'))
                )
                db.session.add(prod)
                db.session.flush()  # Get ID without committing

                # Handle image upload
                image_upload_ok = True
                try:
                    image_path = save_product_image(image, prod.id)
                    if image_path:
                        prod.image = image_path
                except ValueError as e:
                    flash(str(e), 'error')
                    image_upload_ok = False

                if image_upload_ok:
                    db.session.commit()
                    flash('Produk berhasil ditambahkan.', 'success')
                    return redirect(url_for('admin.produk'))
                else:
                    db.session.rollback()
    return render_template('dashboard/produk_form.html', categories=categories, product=None)


@bp.route('/produk/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def produk_edit(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        description = request.form.get('description', '').strip()
        price = request.form.get('price', type=int)
        stock = request.form.get('stock', type=int)
        image = request.files.get('image')

        errors = []
        if not name:
            errors.append('Nama produk wajib diisi.')
        if not category_id:
            errors.append('Kategori wajib dipilih.')
        if price is None or price < 0:
            errors.append('Harga tidak valid.')
        if stock is None or stock < 0:
            errors.append('Stok tidak valid.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            slug = name.lower().replace(' ', '-')
            existing = Product.query.filter(Product.slug == slug, Product.id != id).first()
            if existing:
                flash('Produk dengan nama serupa sudah ada.', 'error')
            else:
                product.category_id = category_id
                product.name = name
                product.slug = slug
                product.description = description
                product.price = price
                product.stock = stock
                product.is_featured = bool(request.form.get('is_featured'))

                # Handle image upload (only if new file provided)
                if image and image.filename:
                    try:
                        # Delete old image file if exists
                        if product.image:
                            old_path = os.path.join(current_app.root_path, product.image)
                            if os.path.exists(old_path):
                                os.remove(old_path)

                        image_path = save_product_image(image, product.id)
                        if image_path:
                            product.image = image_path
                    except ValueError as e:
                        flash(str(e), 'error')

                db.session.commit()
                flash('Produk berhasil diperbarui.', 'success')
                return redirect(url_for('admin.produk'))
    return render_template('dashboard/produk_form.html', categories=categories, product=product)


@bp.route('/produk/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def produk_toggle(id):
    product = Product.query.get_or_404(id)
    product.is_active = not product.is_active
    db.session.commit()
    flash(f'Produk {"diaktifkan" if product.is_active else "dinonaktifkan"}.', 'success')
    return redirect(url_for('admin.produk'))


@bp.route('/produk/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def produk_delete(id):
    product = Product.query.get_or_404(id)
    # Delete image file if exists
    if product.image:
        image_path = os.path.join(current_app.root_path, product.image)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(product)
    db.session.commit()
    flash('Produk berhasil dihapus.', 'success')
    return redirect(url_for('admin.produk'))


@bp.route('/pelanggan')
@login_required
@admin_required
def pelanggan():
    """List customers with filtering, search, and pagination."""
    from sqlalchemy import or_, func

    # Query parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    role_filter = request.args.get('role', '').strip()
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('q', '').strip()

    # Base query
    query = User.query

    # Role filter
    if role_filter in ['customer', 'admin']:
        query = query.filter(User.role == role_filter)

    # Status filter (is_active)
    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)

    # Search by name, username, email
    if search:
        query = query.filter(
            or_(
                User.fullname.ilike(f'%{search}%'),
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
            )
        )

    # Order by created_at desc
    query = query.order_by(User.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items

    # Get order counts for each user
    user_order_counts = {}
    if users:
        user_ids = [u.id for u in users]
        order_counts = db.session.query(
            Order.user_id, func.count(Order.id)
        ).filter(
            Order.user_id.in_(user_ids)
        ).group_by(Order.user_id).all()
        user_order_counts = {uc[0]: uc[1] for uc in order_counts}

    # Summary counts
    total_customers = User.query.filter_by(role='customer').count()
    active_customers = User.query.filter_by(role='customer', is_active=True).count()
    inactive_customers = User.query.filter_by(role='customer', is_active=False).count()
    total_admins = User.query.filter_by(role='admin').count()

    return render_template('dashboard/pelanggan.html',
        users=users,
        pagination=pagination,
        role_filter=role_filter,
        status_filter=status_filter,
        search=search,
        user_order_counts=user_order_counts,
        total_customers=total_customers,
        active_customers=active_customers,
        inactive_customers=inactive_customers,
        total_admins=total_admins,
    )


@bp.route('/pelanggan/<int:user_id>/activate', methods=['POST'])
@login_required
@admin_required
def pelanggan_activate(user_id):
    """Activate a user account."""
    user = db.session.get(User, user_id)
    if not user:
        flash('Pengguna tidak ditemukan.', 'error')
        return redirect(url_for('admin.pelanggan'))

    # Prevent self-deactivation
    if user.id == current_user.id:
        flash('Tidak bisa mengaktifkan akun sendiri.', 'error')
        return redirect(url_for('admin.pelanggan'))

    if user.is_active:
        flash('Pengguna sudah aktif.', 'info')
        return redirect(url_for('admin.pelanggan'))

    user.is_active = True
    db.session.commit()

    # Audit log
    log_auth_event(
        event='user_activated',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'User {user.username} (ID: {user.id}) activated by admin'
    )

    flash('Pengguna diaktifkan.', 'success')
    return redirect(url_for('admin.pelanggan'))


@bp.route('/pelanggan/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def pelanggan_deactivate(user_id):
    """Deactivate a user account."""
    user = db.session.get(User, user_id)
    if not user:
        flash('Pengguna tidak ditemukan.', 'error')
        return redirect(url_for('admin.pelanggan'))

    # Prevent self-deactivation
    if user.id == current_user.id:
        flash('Tidak bisa menonaktifkan akun sendiri.', 'error')
        return redirect(url_for('admin.pelanggan'))

    # Prevent deactivating last admin
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin', is_active=True).count()
        if admin_count <= 1:
            flash('Tidak bisa menonaktifkan admin terakhir.', 'error')
            return redirect(url_for('admin.pelanggan'))

    if not user.is_active:
        flash('Pengguna sudah nonaktif.', 'info')
        return redirect(url_for('admin.pelanggan'))

    user.is_active = False
    db.session.commit()

    # Audit log
    log_auth_event(
        event='user_deactivated',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'User {user.username} (ID: {user.id}) deactivated by admin'
    )

    flash('Pengguna dinonaktifkan.', 'success')
    return redirect(url_for('admin.pelanggan'))


@bp.route('/pelanggan/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def pelanggan_delete(user_id):
    """Delete a user account (only if no orders)."""
    user = db.session.get(User, user_id)
    if not user:
        flash('Pengguna tidak ditemukan.', 'error')
        return redirect(url_for('admin.pelanggan'))

    # Prevent self-deletion
    if user.id == current_user.id:
        flash('Tidak bisa menghapus akun sendiri.', 'error')
        return redirect(url_for('admin.pelanggan'))

    # Prevent deleting last admin
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Tidak bisa menghapus admin terakhir.', 'error')
            return redirect(url_for('admin.pelanggan'))

    # Check if user has orders
    order_count = Order.query.filter_by(user_id=user.id).count()
    if order_count > 0:
        flash('Tidak bisa menghapus pengguna yang memiliki pesanan. Gunakan nonaktifkan sebagai gantinya.', 'error')
        return redirect(url_for('admin.pelanggan'))

    # Delete related OTPs first (avoid FK constraint violation)
    from app.models import EmailOTP
    EmailOTP.query.filter_by(user_id=user.id).delete()

    username = user.username
    user_id_val = user.id
    db.session.delete(user)
    db.session.commit()

    # Audit log
    log_auth_event(
        event='user_deleted',
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status='success',
        reason=f'User {username} (ID: {user_id_val}) deleted by admin'
    )

    flash('Pengguna dihapus.', 'success')
    return redirect(url_for('admin.pelanggan'))


@bp.route('/laporan')
@login_required
@admin_required
def laporan():
    """Transaction reports with date range filter and export."""
    from sqlalchemy import func
    from datetime import date, datetime, timedelta
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, numbers
    from openpyxl.utils import get_column_letter

    # Indonesian month names
    ID_MONTHS = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ]

    def format_id_date(d):
        """Format date with Indonesian month name."""
        return f'{d.day} {ID_MONTHS[d.month - 1]} {d.year}'

    # Default date range: current month
    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    # Get query parameters
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    export_format = request.args.get('export', '').strip()

    # Parse dates
    try:
        if date_from:
            start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        else:
            start_date = default_start
    except ValueError:
        start_date = default_start

    try:
        if date_to:
            end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            end_date = default_end
    except ValueError:
        end_date = default_end

    # Validate date range
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # Base query for completed orders (paid, processing, delivered)
    completed_statuses = [Order.STATUS_PAID, Order.STATUS_PROCESSING, Order.STATUS_DELIVERED]
    base_query = Order.query.filter(
        Order.status.in_(completed_statuses),
        func.date(Order.created_at) >= start_date,
        func.date(Order.created_at) <= end_date
    )

    # Total revenue
    total_revenue = base_query.with_entities(func.sum(Order.total_price)).scalar() or 0

    # Order count
    order_count = base_query.count()

    # Average order value
    avg_order_value = total_revenue / order_count if order_count > 0 else 0

    # Revenue per day
    days_in_range = (end_date - start_date).days + 1
    revenue_per_day = total_revenue / days_in_range if days_in_range > 0 else 0

    # Revenue by payment method
    revenue_by_method = db.session.query(
        Order.payment_method,
        func.sum(Order.total_price),
        func.count(Order.id)
    ).filter(
        Order.status.in_(completed_statuses),
        func.date(Order.created_at) >= start_date,
        func.date(Order.created_at) <= end_date
    ).group_by(Order.payment_method).all()

    # Best-selling products (from OrderItem snapshots)
    best_products = db.session.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label('total_qty'),
        func.sum(OrderItem.subtotal).label('total_revenue')
    ).join(Order).filter(
        Order.status.in_(completed_statuses),
        func.date(Order.created_at) >= start_date,
        func.date(Order.created_at) <= end_date
    ).group_by(OrderItem.product_name).order_by(func.sum(OrderItem.quantity).desc()).limit(10).all()

    # Daily revenue for chart
    daily_revenue = db.session.query(
        func.date(Order.created_at).label('order_date'),
        func.sum(Order.total_price).label('daily_total')
    ).filter(
        Order.status.in_(completed_statuses),
        func.date(Order.created_at) >= start_date,
        func.date(Order.created_at) <= end_date
    ).group_by(func.date(Order.created_at)).order_by(func.date(Order.created_at)).all()

    # Handle export
    if export_format == 'excel':
        wb = Workbook()

        # Styles
        header_font = Font(bold=True)
        title_font = Font(bold=True, size=14)
        subtitle_font = Font(bold=True, size=11)
        header_fill_font = Font(bold=True, color='FFFFFF')
        header_fill = None  # We'll use font color instead
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        idr_format = 'Rp #,##0'

        # --- Sheet 1: Ringkasan ---
        ws1 = wb.active
        ws1.title = 'Ringkasan'

        ws1['A1'] = 'Laporan Transaksi Catering Batam'
        ws1['A1'].font = title_font
        ws1['A2'] = f'Periode: {format_id_date(start_date)} - {format_id_date(end_date)}'
        ws1['A2'].font = subtitle_font

        row = 4
        ws1.cell(row=row, column=1, value='Ringkasan').font = header_font
        row += 1
        headers = ['Item', 'Nilai']
        for col_idx, h in enumerate(headers, 1):
            cell = ws1.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.border = thin_border
        row += 1

        summary_data = [
            ('Total Omzet', total_revenue, idr_format),
            ('Jumlah Pesanan', order_count, None),
            ('Rata-rata per Pesanan', avg_order_value, idr_format),
            ('Rata-rata Omzet per Hari', revenue_per_day, idr_format),
        ]
        for label, val, fmt in summary_data:
            ws1.cell(row=row, column=1, value=label).border = thin_border
            cell_val = ws1.cell(row=row, column=2, value=val)
            cell_val.border = thin_border
            if fmt:
                cell_val.number_format = fmt
            row += 1

        # Auto-fit columns
        ws1.column_dimensions['A'].width = 35
        ws1.column_dimensions['B'].width = 25

        # --- Sheet 2: Metode Pembayaran ---
        ws2 = wb.create_sheet('Metode Pembayaran')
        ws2['A1'] = 'Omzet per Metode Pembayaran'
        ws2['A1'].font = title_font
        ws2['A2'] = f'Periode: {format_id_date(start_date)} - {format_id_date(end_date)}'
        ws2['A2'].font = subtitle_font

        row = 4
        headers = ['Metode', 'Omzet', 'Jumlah Pesanan', 'Persentase']
        for col_idx, h in enumerate(headers, 1):
            cell = ws2.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.border = thin_border
        row += 1

        for method, rev, cnt in revenue_by_method:
            ws2.cell(row=row, column=1, value=method.capitalize()).border = thin_border
            cell_rev = ws2.cell(row=row, column=2, value=rev)
            cell_rev.border = thin_border
            cell_rev.number_format = idr_format
            ws2.cell(row=row, column=3, value=cnt).border = thin_border
            pct = (rev / total_revenue * 100) if total_revenue > 0 else 0
            cell_pct = ws2.cell(row=row, column=4, value=pct / 100)
            cell_pct.border = thin_border
            cell_pct.number_format = '0.00%'
            row += 1

        ws2.column_dimensions['A'].width = 20
        ws2.column_dimensions['B'].width = 25
        ws2.column_dimensions['C'].width = 20
        ws2.column_dimensions['D'].width = 15

        # --- Sheet 3: Produk Terlaris ---
        ws3 = wb.create_sheet('Produk Terlaris')
        ws3['A1'] = 'Produk Terlaris'
        ws3['A1'].font = title_font
        ws3['A2'] = f'Periode: {format_id_date(start_date)} - {format_id_date(end_date)}'
        ws3['A2'].font = subtitle_font

        row = 4
        headers = ['No', 'Produk', 'Qty Terjual', 'Omzet']
        for col_idx, h in enumerate(headers, 1):
            cell = ws3.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.border = thin_border
        row += 1

        for idx, (name, qty, rev) in enumerate(best_products, 1):
            ws3.cell(row=row, column=1, value=idx).border = thin_border
            ws3.cell(row=row, column=2, value=name).border = thin_border
            ws3.cell(row=row, column=3, value=qty).border = thin_border
            cell_rev = ws3.cell(row=row, column=4, value=rev)
            cell_rev.border = thin_border
            cell_rev.number_format = idr_format
            row += 1

        ws3.column_dimensions['A'].width = 8
        ws3.column_dimensions['B'].width = 40
        ws3.column_dimensions['C'].width = 15
        ws3.column_dimensions['D'].width = 25

        # --- Sheet 4: Omzet Harian ---
        ws4 = wb.create_sheet('Omzet Harian')
        ws4['A1'] = 'Rata-rata Omzet per Hari'
        ws4['A1'].font = title_font
        ws4['A2'] = f'Periode: {format_id_date(start_date)} - {format_id_date(end_date)}'
        ws4['A2'].font = subtitle_font

        row = 4
        headers = ['Tanggal', 'Omzet']
        for col_idx, h in enumerate(headers, 1):
            cell = ws4.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.border = thin_border
        row += 1

        for dr in daily_revenue:
            cell_date = ws4.cell(row=row, column=1, value=dr.order_date)
            cell_date.border = thin_border
            cell_date.number_format = 'DD MMMM YYYY'
            cell_rev = ws4.cell(row=row, column=2, value=dr.daily_total)
            cell_rev.border = thin_border
            cell_rev.number_format = idr_format
            row += 1

        ws4.column_dimensions['A'].width = 25
        ws4.column_dimensions['B'].width = 25

        # --- Sheet 5: Detail Pesanan ---
        ws5 = wb.create_sheet('Detail Pesanan')
        ws5['A1'] = 'Detail Pesanan (Status: Dibayar, Diproses, Selesai)'
        ws5['A1'].font = title_font
        ws5['A2'] = f'Periode: {format_id_date(start_date)} - {format_id_date(end_date)}'
        ws5['A2'].font = subtitle_font

        # Get orders for detail table
        orders = base_query.order_by(Order.created_at.desc()).all()

        row = 4
        headers = ['Kode Pesanan', 'Pelanggan', 'Email', 'Tanggal Pesan', 'Metode Bayar', 'Status', 'Total']
        for col_idx, h in enumerate(headers, 1):
            cell = ws5.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.border = thin_border
        row += 1

        for order in orders:
            ws5.cell(row=row, column=1, value=order.order_code).border = thin_border
            ws5.cell(row=row, column=2, value=order.user.fullname).border = thin_border
            ws5.cell(row=row, column=3, value=order.user.email).border = thin_border
            cell_date = ws5.cell(row=row, column=4, value=order.created_at)
            cell_date.border = thin_border
            cell_date.number_format = 'DD/MM/YYYY HH:MM'
            ws5.cell(row=row, column=5, value=order.payment_method.capitalize()).border = thin_border
            ws5.cell(row=row, column=6, value=order.status_label).border = thin_border
            cell_total = ws5.cell(row=row, column=7, value=order.total_price)
            cell_total.border = thin_border
            cell_total.number_format = idr_format
            row += 1

        ws5.column_dimensions['A'].width = 22
        ws5.column_dimensions['B'].width = 25
        ws5.column_dimensions['C'].width = 30
        ws5.column_dimensions['D'].width = 22
        ws5.column_dimensions['E'].width = 18
        ws5.column_dimensions['F'].width = 18
        ws5.column_dimensions['G'].width = 25

        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        from flask import make_response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=laporan_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.xlsx'
        return response

    if export_format == 'pdf':
        # Render print-friendly HTML for PDF
        # Get current time in Asia/Jakarta (UTC+7)
        from datetime import timezone, timedelta
        jakarta_tz = timezone(timedelta(hours=7))
        printed_at = datetime.now(jakarta_tz).strftime('%d %B %Y %H:%M')
        return render_template('dashboard/laporan_pdf.html',
            start_date=start_date,
            end_date=end_date,
            total_revenue=total_revenue,
            order_count=order_count,
            avg_order_value=avg_order_value,
            revenue_per_day=revenue_per_day,
            revenue_by_method=revenue_by_method,
            best_products=best_products,
            daily_revenue=daily_revenue,
            format_id_date=format_id_date,
            printed_at=printed_at,
        )

    # Get orders for detail table
    orders = base_query.order_by(Order.created_at.desc()).all()

    return render_template('dashboard/laporan.html',
        date_from=start_date.strftime('%Y-%m-%d'),
        date_to=end_date.strftime('%Y-%m-%d'),
        start_date_obj=start_date,
        end_date_obj=end_date,
        total_revenue=total_revenue,
        order_count=order_count,
        avg_order_value=avg_order_value,
        revenue_per_day=revenue_per_day,
        revenue_by_method=revenue_by_method,
        best_products=best_products,
        daily_revenue=daily_revenue,
        orders=orders,
        format_id_date=format_id_date,
    )


@bp.route('/ulasan/<int:review_id>/delete', methods=['POST'])
@login_required
@admin_required
def ulasan_delete(review_id):
    from app.models import Review
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    flash('Ulasan dihapus.', 'success')
    return redirect(url_for('admin.ulasan'))


@bp.route('/ulasan')
@login_required
@admin_required
def ulasan():
    from app.models import Review
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    # Calculate stats
    total_reviews = len(reviews)
    avg_rating = sum(r.rating for r in reviews) / total_reviews if total_reviews > 0 else 0
    five_star = sum(1 for r in reviews if r.rating == 5)
    four_star = sum(1 for r in reviews if r.rating == 4)
    return render_template('dashboard/ulasan.html',
        reviews=reviews,
        total_reviews=total_reviews,
        avg_rating=round(avg_rating, 1),
        five_star=five_star,
        four_star=four_star,
    )


@bp.route('/pengaturan')
@login_required
@admin_required
def pengaturan():
    from app.models import Setting
    # Get or create settings
    settings = {}
    for key in ['store_name', 'whatsapp', 'address', 'hours', 'free_delivery', 'qris_active', 'cod_active']:
        s = Setting.query.get(key)
        settings[key] = s.value if s else ''
    return render_template('dashboard/pengaturan.html', settings=settings)


# --- Promo Banner CRUD ---
@bp.route('/promo')
@login_required
@admin_required
def promo_list():
    banners = PromoBanner.query.order_by(PromoBanner.display_order, PromoBanner.id).all()
    return render_template('dashboard/promo_list.html', banners=banners)


@bp.route('/promo/create', methods=['GET', 'POST'])
@login_required
@admin_required
def promo_create():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    if request.method == 'POST':
        headline = request.form.get('headline', '').strip()
        subtitle = request.form.get('subtitle', '').strip()
        badge = request.form.get('badge', '').strip()
        price = request.form.get('price', type=int)
        unit = request.form.get('unit', '').strip()
        cta_label = request.form.get('cta_label', '').strip() or 'Pesan Sekarang'
        product_id = request.form.get('product_id', type=int)
        cta_url = request.form.get('cta_url', '').strip()
        display_order = request.form.get('display_order', type=int) or 0
        is_active = bool(request.form.get('is_active'))
        starts_at = request.form.get('starts_at')
        ends_at = request.form.get('ends_at')
        image = request.files.get('image')

        errors = []
        if not headline:
            errors.append('Judul wajib diisi.')
        if not image or not image.filename:
            errors.append('Gambar wajib diunggah.')
        if price is not None and price < 0:
            errors.append('Harga tidak valid.')

        # Validate cta_url
        valid_url, url_error = validate_cta_url(cta_url)
        if not valid_url:
            errors.append(url_error)

        # Validate dates
        if starts_at:
            try:
                starts_at = datetime.fromisoformat(starts_at)
            except ValueError:
                errors.append('Format tanggal mulai tidak valid.')
        if ends_at:
            try:
                ends_at = datetime.fromisoformat(ends_at)
            except ValueError:
                errors.append('Format tanggal berakhir tidak valid.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            # Handle image upload
            image_upload_ok = True
            try:
                image_path = save_promo_image(image)
                if not image_path:
                    errors.append('Gambar wajib diunggah.')
                    image_upload_ok = False
            except ValueError as e:
                flash(str(e), 'error')
                image_upload_ok = False

            if image_upload_ok:
                banner = PromoBanner(
                    headline=headline,
                    subtitle=subtitle or None,
                    badge=badge or None,
                    image=image_path,
                    alt_text=request.form.get('alt_text', '').strip() or headline,
                    price=price,
                    unit=unit or None,
                    cta_label=cta_label,
                    product_id=product_id if product_id else None,
                    cta_url=cta_url if cta_url else None,
                    display_order=display_order,
                    is_active=is_active,
                    starts_at=starts_at,
                    ends_at=ends_at,
                )
                db.session.add(banner)
                db.session.commit()
                flash('Banner promo berhasil ditambahkan.', 'success')
                return redirect(url_for('admin.promo_list'))

    return render_template('dashboard/promo_form.html', banner=None, products=products)


@bp.route('/promo/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def promo_edit(id):
    banner = PromoBanner.query.get_or_404(id)
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    if request.method == 'POST':
        headline = request.form.get('headline', '').strip()
        subtitle = request.form.get('subtitle', '').strip()
        badge = request.form.get('badge', '').strip()
        price = request.form.get('price', type=int)
        unit = request.form.get('unit', '').strip()
        cta_label = request.form.get('cta_label', '').strip() or 'Pesan Sekarang'
        product_id = request.form.get('product_id', type=int)
        cta_url = request.form.get('cta_url', '').strip()
        display_order = request.form.get('display_order', type=int) or 0
        is_active = bool(request.form.get('is_active'))
        starts_at = request.form.get('starts_at')
        ends_at = request.form.get('ends_at')
        image = request.files.get('image')

        errors = []
        if not headline:
            errors.append('Judul wajib diisi.')
        if price is not None and price < 0:
            errors.append('Harga tidak valid.')

        # Validate cta_url
        valid_url, url_error = validate_cta_url(cta_url)
        if not valid_url:
            errors.append(url_error)

        # Validate dates
        if starts_at:
            try:
                starts_at = datetime.fromisoformat(starts_at)
            except ValueError:
                errors.append('Format tanggal mulai tidak valid.')
        if ends_at:
            try:
                ends_at = datetime.fromisoformat(ends_at)
            except ValueError:
                errors.append('Format tanggal berakhir tidak valid.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            banner.headline = headline
            banner.subtitle = subtitle or None
            badge = badge or None
            banner.badge = badge
            banner.price = price
            banner.unit = unit or None
            banner.cta_label = cta_label
            banner.product_id = product_id if product_id else None
            banner.cta_url = cta_url if cta_url else None
            banner.display_order = display_order
            banner.is_active = is_active
            banner.starts_at = starts_at
            banner.ends_at = ends_at
            banner.alt_text = request.form.get('alt_text', '').strip() or headline

            # Handle image upload (only if new file provided)
            if image and image.filename:
                try:
                    # Delete old image file if exists
                    if banner.image:
                        old_path = os.path.join(current_app.root_path, banner.image)
                        if os.path.exists(old_path):
                            os.remove(old_path)

                    image_path = save_promo_image(image, banner.id)
                    if image_path:
                        banner.image = image_path
                except ValueError as e:
                    flash(str(e), 'error')

            db.session.commit()
            flash('Banner promo berhasil diperbarui.', 'success')
            return redirect(url_for('admin.promo_list'))
    return render_template('dashboard/promo_form.html', banner=banner, products=products)


@bp.route('/promo/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def promo_toggle(id):
    banner = PromoBanner.query.get_or_404(id)
    banner.is_active = not banner.is_active
    db.session.commit()
    flash(f'Banner promo {"diaktifkan" if banner.is_active else "dinonaktifkan"}.', 'success')
    return redirect(url_for('admin.promo_list'))


@bp.route('/promo/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def promo_delete(id):
    banner = PromoBanner.query.get_or_404(id)
    # Delete image file if exists
    if banner.image:
        image_path = os.path.join(current_app.root_path, banner.image)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(banner)
    db.session.commit()
    flash('Banner promo berhasil dihapus.', 'success')
    return redirect(url_for('admin.promo_list'))