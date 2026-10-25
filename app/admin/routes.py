"""Admin Routes - Dashboard & Management"""

from functools import wraps
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Category, Product, PromoBanner
from app.admin import bp
from werkzeug.utils import secure_filename
from PIL import Image
import os
import uuid
from urllib.parse import urlparse
from datetime import datetime


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
    return render_template('dashboard/ringkasan.html')


@bp.route('/pesanan')
@login_required
@admin_required
def pesanan():
    return render_template('dashboard/pesanan.html')


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
    return render_template('dashboard/kategori.html', categories=categories)


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
                    is_active=True
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
    return render_template('dashboard/pelanggan.html')


@bp.route('/laporan')
@login_required
@admin_required
def laporan():
    return render_template('dashboard/laporan.html')


@bp.route('/ulasan')
@login_required
@admin_required
def ulasan():
    return render_template('dashboard/ulasan.html')


@bp.route('/pengaturan')
@login_required
@admin_required
def pengaturan():
    return render_template('dashboard/pengaturan.html')


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