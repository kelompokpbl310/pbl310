"""Main Routes - Public Pages"""

from flask import render_template, url_for, request, redirect, flash, session
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Product, User, Category, MenuType, Review
from werkzeug.utils import secure_filename
from PIL import Image
import os
import uuid


# Sample products for catalog (static sample data until DB is seeded)
SAMPLE_PRODUCTS = [
    dict(name='Sate Kambing Bumbu Kacang', desc='Sate empuk dengan bumbu kacang khas, dibakar arang kelapa', price=38000, unit='10 tusuk', rating='5,0', reviews=48, img='img/assets4.png', category='Sate'),
    dict(name='Nasi Kebuli Rempah Nusantara', desc='Aroma rempah khas Timur Tengah, gurih dan kaya rasa', price=40000, unit='1 porsi', rating='4,9', reviews=62, img='img/assets2.png', category='Kebuli'),
    dict(name='Gulai Kambing Santan Premium', desc='Kuah santan rempah kental tanpa bau prengus', price=42000, unit='1 porsi', rating='4,9', reviews=35, img='img/assets3.png', category='Gulai'),
    dict(name='Kambing Guling Utuh Spesial', desc='Pilihan utama pesta dan syukuran keluarga besar', price=2450000, unit='1 ekor', rating='5,0', reviews=24, img='img/assets1.png', category='Guling'),
    dict(name='Nasi Mandhi Kambing Komplit', desc='Nasi rempah Arab dengan lauk kambing gurih', price=44000, unit='1 porsi', rating='4,8', reviews=41, img='img/assets2.png', category='Kebuli'),
    dict(name='Sate Kecap Manis Pedas', desc='Perpaduan manis kecap dan pedas cabai rawit', price=38000, unit='10 tusuk', rating='4,9', reviews=37, img='img/assets4.png', category='Sate'),
    dict(name='Sop Kaki Kambing Rempah', desc='Kuah bening gurih dengan rempah hangat', price=39000, unit='1 porsi', rating='4,8', reviews=28, img='img/assets3.png', category='Gulai'),
    dict(name='Paket Prasmanan Aqiqah', desc='Paket lengkap untuk syukuran bersamaan', price=2750000, unit='paket', rating='5,0', reviews=19, img='img/assets1.png', category='Prasmanan'),
    dict(name='Gulai Kambing Muda Empuk', desc='Daging muda empuk, kuah gulai pekat rempah', price=43000, unit='1 porsi', rating='4,9', reviews=33, img='img/assets3.png', category='Gulai'),
    dict(name='Tongseng Kambing Kuah Kuning', desc='Tongseng gurih dengan kol dan cabai segar', price=41000, unit='1 porsi', rating='4,8', reviews=30, img='img/assets4.png', category='Gulai'),
]

# Promo slides data (static for now)
PROMO_SLIDES = [
    dict(badge='TERLARIS', headline='Nasi Kebuli Kambing',
         subtitle='Menu favorit pelanggan aqiqah. Bumbu rempah, daging empuk.',
         price=40000, unit='/box', cta='Lihat Produk',
         cta_endpoint='main.produk', img='img/assets2.png',
         alt='Nasi kebuli kambing dengan lauk, menu aqiqah terlaris'),
    dict(badge='HEMAT', headline='Paket Aqiqah Hemat',
         subtitle='Pas untuk syukuran sederhana, tetap lezat dan berkesan.',
         price=38000, unit='', cta='Lihat Produk',
         cta_endpoint='main.produk', img='img/banners/paket-hemat.png',
         alt='Paket aqiqah hemat untuk syukuran sederhana'),
    dict(badge='LENGKAP', headline='Paket Aqiqah Lengkap',
         subtitle='Dimasak, dikemas, dan diantar. Anak laki-laki 2 ekor, perempuan 1 ekor.',
         price=2750000, unit='', cta='Lihat Paket',
         cta_endpoint='main.produk', cta_anchor='katalog',
         img='img/banners/paket-lengkap.png',
         alt='Paket aqiqah lengkap dengan layanan antar'),
    dict(badge='FAVORIT', headline='Sate Kambing Empuk',
         subtitle='Daging empuk bumbu kacang, dibakar arang kelapa.',
         price=38000, unit='/10 tusuk', cta='Lihat Produk',
         cta_endpoint='main.produk', img='img/assets4.png',
         alt='Sate kambing empuk dengan bumbu kacang'),
    dict(badge='SPESIAL', headline='Kambing Guling Utuh',
         subtitle='Panggang utuh untuk pesta dan syukuran besar.',
         price=2450000, unit='/ekor', cta='Lihat Produk',
         cta_endpoint='main.produk', img='img/assets1.png',
         alt='Kambing guling utuh siap saji'),
]


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
    slides = []
    for s in PROMO_SLIDES:
        item = dict(s)
        if s.get('cta_anchor'):
            item['cta_url'] = url_for(s['cta_endpoint'], _anchor=s['cta_anchor'])
        else:
            item['cta_url'] = url_for(s['cta_endpoint'])
        slides.append(item)
    
    # Get active menu types for filter tabs
    menu_types = MenuType.query.filter_by(is_active=True).order_by(MenuType.display_order).all()
    
    # Get active products from DB
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
    
    # Get featured products for "Produk Populer"
    featured_products = Product.query.filter_by(is_active=True, is_featured=True).limit(2).all()
    
    # Convert DB products to dict format for template compatibility
    def product_to_dict(p):
        return dict(
            id=p.id,
            name=p.name,
            desc=p.description or '',
            price=p.price,
            unit=p.stock > 0 and '1 porsi' or 'Habis',  # simple stock indicator
            rating='5,0',  # could add Review model later
            reviews=0,
            img=p.image.replace('static/', '') if p.image else 'img/assets1.png',
            category=p.menu_type.name if p.menu_type else 'Lainnya'
        )
    
    featured_products = [product_to_dict(p) for p in featured_products]
    all_products = [product_to_dict(p) for p in products]
    
    return render_template('produk.html', 
                           promo_slides=slides,
                           menu_types=menu_types,
                           featured_products=featured_products,
                           all_products=all_products)


@bp.route('/detail-produk/<int:id>')
def detail_produk(id):
    product = Product.query.filter_by(id=id, is_active=True).first_or_404()
    
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


@bp.route('/checkout')
def checkout():
    return render_template('checkout.html')


# --- Cart Routes ---

def _get_cart():
    """Get cart from session, initialize if not exists."""
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']


def _save_cart(cart):
    """Save cart to session and mark modified."""
    session['cart'] = cart
    session.modified = True


@bp.route('/keranjang')
def cart():
    """Display cart page with items from session."""
    cart = _get_cart()
    cart_items = []
    cart_subtotal = 0

    if cart:
        product_ids = [int(pid) for pid in cart.keys()]
        products = Product.query.filter(Product.id.in_(product_ids), Product.is_active == True).all()
        product_map = {p.id: p for p in products}

        for pid_str, qty in cart.items():
            pid = int(pid_str)
            product = product_map.get(pid)
            if not product:
                continue  # Skip deleted/inactive products
            
            # Limit quantity to stock
            max_qty = product.stock if product.stock > 0 else 99
            qty = min(qty, max_qty)
            
            subtotal = product.price * qty
            cart_subtotal += subtotal
            
            cart_items.append({
                'product_id': product.id,
                'name': product.name,
                'price': product.price,
                'quantity': qty,
                'subtotal': subtotal,
                'unit': product.stock > 0 and '1 porsi' or 'Habis',
                'stock': product.stock,
                'image': product.image or 'img/assets1.png',
                'menu_type': product.menu_type.name if product.menu_type else None,
            })

    cart_total = cart_subtotal  # Shipping is free

    return render_template('cart.html',
                           cart_items=cart_items,
                           cart_subtotal=cart_subtotal,
                           cart_total=cart_total)


@bp.route('/keranjang/tambah', methods=['GET', 'POST'])
def cart_add():
    """Add product to cart (from detail page or product listing)."""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', 1, type=int)
    else:
        product_id = request.args.get('product_id', type=int)
        quantity = request.args.get('quantity', 1, type=int)

    if not product_id:
        flash('Produk tidak valid.', 'error')
        return redirect(request.referrer or url_for('main.produk'))

    product = Product.query.filter_by(id=product_id, is_active=True).first()
    if not product:
        flash('Produk tidak ditemukan.', 'error')
        return redirect(request.referrer or url_for('main.produk'))

    if product.stock > 0 and quantity > product.stock:
        flash(f'Stok tersedia hanya {product.stock}.', 'error')
        return redirect(request.referrer or url_for('main.detail_produk', id=product_id))

    cart = _get_cart()
    pid_str = str(product_id)
    current_qty = cart.get(pid_str, 0)
    new_qty = current_qty + quantity

    # Limit to stock
    max_qty = product.stock if product.stock > 0 else 99
    if new_qty > max_qty:
        new_qty = max_qty

    cart[pid_str] = new_qty
    _save_cart(cart)

    flash(f'{product.name} ditambahkan ke keranjang.', 'success')
    return redirect(url_for('main.cart'))


@bp.route('/keranjang/update', methods=['POST'])
def cart_update():
    """Update cart quantities or remove items."""
    cart = _get_cart()

    # Cart template sends name="clear" value="1"; keep action=clear for older clients.
    if request.form.get('clear') or request.form.get('action') == 'clear':
        _save_cart({})
        flash('Keranjang dikosongkan.', 'success')
        return redirect(url_for('main.cart'))

    # Handle remove button
    remove_id = request.form.get('remove')
    if remove_id:
        # Cart keys are strings, but form value might be int or string
        pid_str = str(remove_id)
        if pid_str in cart:
            product = Product.query.get(int(pid_str))
            name = product.name if product else 'Produk'
            del cart[pid_str]
            _save_cart(cart)
            flash(f'{name} dihapus dari keranjang.', 'success')
        return redirect(url_for('main.cart'))

    # Update quantities from inputs (quantities[pid] fields)
    updated = False
    for pid_str, qty_str in request.form.items():
        if pid_str.startswith('quantities[') and pid_str.endswith(']'):
            pid = pid_str[11:-1]  # Extract product_id from 'quantities[ID]'
            try:
                qty = int(qty_str)
                if qty > 0:
                    product = Product.query.get(int(pid))
                    if product:
                        max_qty = product.stock if product.stock > 0 else 99
                        qty = min(qty, max_qty)
                        cart[pid] = qty
                        updated = True
            except (ValueError, TypeError):
                pass

    if updated:
        _save_cart(cart)
        flash('Keranjang diperbarui.', 'success')

    return redirect(url_for('main.cart'))


@bp.route('/keranjang/hapus/<int:product_id>', methods=['POST'])
def cart_remove(product_id):
    """Remove single item from cart."""
    cart = _get_cart()
    pid_str = str(product_id)
    
    if pid_str in cart:
        product = Product.query.get(product_id)
        name = product.name if product else 'Produk'
        del cart[pid_str]
        _save_cart(cart)
        flash(f'{name} dihapus dari keranjang.', 'success')
    
    return redirect(url_for('main.cart'))


@bp.route('/tentang')
def tentang():
    return render_template('tentang.html')


# --- User Profile Routes ---

UPLOAD_FOLDER = 'app/static/uploads/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/profil')
@login_required
def profil():
    """Akun tab - Profile info + photo upload"""
    return render_template('profil/akun.html')


@bp.route('/profil', methods=['POST'])
@login_required
def profil_update():
    fullname = request.form.get('fullname', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()

    if not fullname:
        flash('Nama lengkap wajib diisi.', 'error')
        return redirect(url_for('main.profil'))

    if not email:
        flash('Email wajib diisi.', 'error')
        return redirect(url_for('main.profil'))

    # Check email uniqueness (excluding current user)
    existing = User.query.filter(User.email == email, User.id != current_user.id).first()
    if existing:
        flash('Email sudah terdaftar.', 'error')
        return redirect(url_for('main.profil'))

    current_user.fullname = fullname
    current_user.email = email
    current_user.phone = phone if phone else None

    db.session.commit()
    flash('Profil berhasil diperbarui.', 'success')
    return redirect(url_for('main.profil'))


@bp.route('/profil/photo', methods=['POST'])
@login_required
def profil_photo():
    if 'avatar' not in request.files:
        flash('Tidak ada file yang diunggah.', 'error')
        return redirect(url_for('main.profil'))

    file = request.files['avatar']
    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'error')
        return redirect(url_for('main.profil'))

    if not allowed_file(file.filename):
        flash('Format file tidak didukung. Gunakan PNG, JPG, atau WebP.', 'error')
        return redirect(url_for('main.profil'))

    # Check file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    if file_length > MAX_FILE_SIZE:
        flash('Ukuran file maksimal 2MB.', 'error')
        return redirect(url_for('main.profil'))

    try:
        # Process image with Pillow
        img = Image.open(file.stream)
        img.verify()  # Verify it's a valid image
        file.seek(0)
        img = Image.open(file.stream)

        # Convert to RGB if needed (for WebP)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize to square (crop center)
        size = min(img.size)
        left = (img.width - size) // 2
        top = (img.height - size) // 2
        img = img.crop((left, top, left + size, top + size))
        img = img.resize((256, 256), Image.Resampling.LANCZOS)

        # Generate unique filename
        ext = 'webp'
        filename = f'user_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}'
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Save as WebP
        img.save(filepath, 'WEBP', quality=85, optimize=True)

        # Update user avatar
        current_user.avatar = f'uploads/avatars/{filename}'
        db.session.commit()

        flash('Foto profil berhasil diubah.', 'success')
    except Exception as e:
        flash('Gagal memproses gambar. Pastikan file adalah gambar valid.', 'error')

    return redirect(url_for('main.profil'))


@bp.route('/profil/keamanan')
@login_required
def profil_keamanan():
    """Keamanan tab - Password change"""
    return render_template('profil/keamanan.html')


@bp.route('/profil/password', methods=['POST'])
@login_required
def profil_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not current_user.check_password(current_password):
        flash('Password saat ini salah.', 'error')
        return redirect(url_for('main.profil_keamanan'))

    if len(new_password) < 8:
        flash('Password baru minimal 8 karakter.', 'error')
        return redirect(url_for('main.profil_keamanan'))

    if new_password != confirm_password:
        flash('Konfirmasi password tidak cocok.', 'error')
        return redirect(url_for('main.profil_keamanan'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password berhasil diubah.', 'success')
    return redirect(url_for('main.profil_keamanan'))


@bp.route('/profil/riwayat')
@login_required
def profil_riwayat():
    """Riwayat Pesanan tab - Order history"""
    return render_template('profil/riwayat.html')