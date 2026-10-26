"""Database Models for Catering Batam"""

from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    avatar = db.Column(db.String(255), nullable=True)  # path to avatar image
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='customer')  # customer, admin
    is_active = db.Column(db.Boolean, default=True, server_default='true', nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


class MenuType(db.Model):
    __tablename__ = 'menu_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(255), nullable=True)  # SVG or image path
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    products = db.relationship('Product', backref='menu_type', lazy=True)

    def __repr__(self):
        return f'<MenuType {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    menu_type_id = db.Column(db.Integer, db.ForeignKey('menu_types.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(255), nullable=True)
    stock = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Customer delivery info
    recipient_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(60), nullable=False)
    delivery_date = db.Column(db.Date, nullable=False)
    delivery_time = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Payment
    payment_method = db.Column(db.String(20), nullable=False)  # 'transfer' or 'cod'

    # Order identification
    order_code = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Status flow: pending_payment -> waiting_verification -> paid -> processing -> delivered
    #              pending_payment -> cancelled (customer)
    #              waiting_verification -> pending_payment (admin reject)
    #              cod orders start at 'processing'
    status = db.Column(db.String(30), nullable=False, default='pending_payment', index=True)

    # Payment proof
    payment_proof = db.Column(db.String(255), nullable=True)
    payment_uploaded_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Totals
    total_price = db.Column(db.Integer, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    # Status constants
    STATUS_PENDING_PAYMENT = 'pending_payment'
    STATUS_WAITING_VERIFICATION = 'waiting_verification'
    STATUS_PAID = 'paid'
    STATUS_PROCESSING = 'processing'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'

    VALID_STATUSES = [
        STATUS_PENDING_PAYMENT,
        STATUS_WAITING_VERIFICATION,
        STATUS_PAID,
        STATUS_PROCESSING,
        STATUS_DELIVERED,
        STATUS_CANCELLED,
    ]

    # Valid transitions: current_status -> list of allowed next statuses
    VALID_TRANSITIONS = {
        STATUS_PENDING_PAYMENT: [STATUS_WAITING_VERIFICATION, STATUS_CANCELLED, STATUS_PROCESSING],  # COD goes to processing
        STATUS_WAITING_VERIFICATION: [STATUS_PAID, STATUS_PENDING_PAYMENT],  # admin approve/reject
        STATUS_PAID: [STATUS_PROCESSING],
        STATUS_PROCESSING: [STATUS_DELIVERED],
        STATUS_DELIVERED: [],
        STATUS_CANCELLED: [],
    }

    def __repr__(self):
        return f'<Order {self.order_code}>'

    @property
    def status_label(self):
        """Indonesian status label for UI."""
        labels = {
            self.STATUS_PENDING_PAYMENT: 'Menunggu Pembayaran',
            self.STATUS_WAITING_VERIFICATION: 'Menunggu Verifikasi',
            self.STATUS_PAID: 'Dibayar',
            self.STATUS_PROCESSING: 'Diproses',
            self.STATUS_DELIVERED: 'Selesai',
            self.STATUS_CANCELLED: 'Dibatalkan',
        }
        return labels.get(self.status, self.status)

    def can_transition_to(self, new_status):
        """Check if transition to new_status is valid."""
        if new_status not in self.VALID_STATUSES:
            return False
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])

    def transition_to(self, new_status):
        """Transition to new_status if valid, else raise ValueError."""
        if not self.can_transition_to(new_status):
            raise ValueError(f'Invalid status transition: {self.status} -> {new_status}')
        self.status = new_status
        self.updated_at = db.func.now()

    def is_pending_payment(self):
        return self.status == self.STATUS_PENDING_PAYMENT

    def is_waiting_verification(self):
        return self.status == self.STATUS_WAITING_VERIFICATION

    def is_paid(self):
        return self.status == self.STATUS_PAID

    def is_processing(self):
        return self.status == self.STATUS_PROCESSING

    def is_delivered(self):
        return self.status == self.STATUS_DELIVERED

    def is_cancelled(self):
        return self.status == self.STATUS_CANCELLED

    def can_customer_cancel(self):
        """Customer can cancel only in pending_payment."""
        return self.status == self.STATUS_PENDING_PAYMENT

    def can_upload_proof(self):
        """Customer can upload proof only for transfer orders in pending_payment."""
        return self.payment_method == 'transfer' and self.status == self.STATUS_PENDING_PAYMENT

    def can_review(self):
        """Check if order is delivered (for review eligibility)."""
        return self.status == self.STATUS_DELIVERED


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    # Snapshot of product at time of purchase
    product_name = db.Column(db.String(100), nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Integer, nullable=False)

    product = db.relationship('Product')

    def __repr__(self):
        return f'<OrderItem {self.id} order={self.order_id} product={self.product_name}>'


class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(200), nullable=True)


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    user = db.relationship('User', backref='reviews')
    product = db.relationship('Product', backref='reviews')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='uq_review_user_product'),
    )

    def __repr__(self):
        return f'<Review {self.id} user={self.user_id} product={self.product_id} rating={self.rating}>'


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    user = db.relationship('User', backref='cart_items')
    product = db.relationship('Product')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='uq_cart_user_product'),
    )

    def __repr__(self):
        return f'<CartItem user={self.user_id} product={self.product_id} qty={self.quantity}>'


class PromoBanner(db.Model):
    __tablename__ = 'promo_banners'
    id = db.Column(db.Integer, primary_key=True)
    headline = db.Column(db.String(120), nullable=False)
    subtitle = db.Column(db.String(255), nullable=True)
    badge = db.Column(db.String(30), nullable=True)
    image = db.Column(db.String(255), nullable=False)  # same path convention as Product.image
    alt_text = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Integer, nullable=True)  # store as integer, not formatted string
    unit = db.Column(db.String(30), nullable=True)
    cta_label = db.Column(db.String(40), nullable=False, default='Pesan Sekarang')
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    cta_url = db.Column(db.String(255), nullable=True)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    product = db.relationship('Product')

    def __repr__(self):
        return f'<PromoBanner {self.headline}>'