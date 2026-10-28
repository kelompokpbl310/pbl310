"""Catering Batam - Flask Application Factory"""

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

# Extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Silakan login untuk mengakses halaman ini.'
login_manager.login_message_category = 'info'


def _configure_logging(app):
    """Configure structured logging for the application."""
    log_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    class ContextFormatter(logging.Formatter):
        """Formatter that adds request context if available."""
        def format(self, record):
            # Add request context if available
            from flask import has_request_context, request
            if has_request_context():
                record.url = request.url
                record.method = request.method
                record.remote_addr = request.remote_addr
                record.user_agent = request.headers.get('User-Agent', '')
            else:
                record.url = ''
                record.method = ''
                record.remote_addr = ''
                record.user_agent = ''
            return super().format(record)

    # File handler with rotation (10MB per file, keep 10 files)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'catering_batam.log'),
        maxBytes=10_000_000,
        backupCount=10
    )
    file_handler.setFormatter(ContextFormatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s | url=%(url)s method=%(method)s ip=%(remote_addr)s ua="%(user_agent)s"'
    ))
    file_handler.setLevel(logging.INFO)

    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ContextFormatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)

    # Configure root logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Catering Batam application startup')

    # Configure security audit logger (separate JSON Lines log)
    from app.security_logging import create_security_audit_logger
    create_security_audit_logger(app)


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    # Payment proof upload folder (outside static for security)
    app.config['PAYMENT_PROOF_UPLOAD_FOLDER'] = os.getenv(
        'PAYMENT_PROOF_UPLOAD_FOLDER',
        os.path.join(app.root_path, '..', 'uploads', 'payments')
    )

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Import models to register them
    from app import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Exempt Midtrans webhook from CSRF
    from app.main.orders import midtrans_notification
    csrf.exempt(midtrans_notification)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Check active user on each request
    @app.before_request
    def check_user_active():
        from flask_login import current_user
        from flask import session
        if current_user.is_authenticated and not current_user.is_active:
            from flask_login import logout_user
            from app.security_logging import log_auth_event
            user_id = current_user.id
            username = current_user.username
            role = current_user.role
            logout_user()
            session.clear()
            log_auth_event(
                event='user_logout',
                user_id=user_id,
                username=username,
                role=role,
                status='success',
                reason='Account deactivated during session'
            )

    # Configure logging
    _configure_logging(app)

    # Template context processors
    @app.context_processor
    def utility_processor():
        ID_MONTHS = [
            'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ]

        def rp(n):
            return 'Rp ' + f'{n:,}'.replace(',', '.')

        def format_id_date(d):
            """Format date with Indonesian month name. Accepts date, datetime, or ISO string."""
            if isinstance(d, str):
                try:
                    d = datetime.strptime(d, '%Y-%m-%d').date()
                except ValueError:
                    return d
            if hasattr(d, 'day') and hasattr(d, 'month') and hasattr(d, 'year'):
                return f'{d.day} {ID_MONTHS[d.month - 1]} {d.year}'
            return str(d)

        return dict(rp=rp, format_id_date=format_id_date)

    # CLI command: flask midtrans-sync
    @app.cli.command('midtrans-sync')
    def midtrans_sync_command():
        """Sync pending Midtrans orders with Midtrans Get Status API."""
        from app.payments import sync_midtrans_status
        from app.models import Order
        from datetime import timedelta, datetime, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        orders = Order.query.filter(
            Order.status == Order.STATUS_PENDING_PAYMENT,
            Order.midtrans_order_id.isnot(None),
            Order.created_at >= cutoff,
        ).all()

        checked = 0
        paid = 0
        cancelled = 0
        unchanged = 0
        errors = 0

        for order in orders:
            try:
                result = sync_midtrans_status(order, source='cron')
                checked += result.get('checked', 0)
                paid += result.get('paid', 0)
                cancelled += result.get('cancelled', 0)
                unchanged += result.get('unchanged', 0)
                errors += result.get('error', 0)
            except Exception as e:
                errors += 1
                app.logger.error(f'midtrans-sync error for {order.order_code}: {e}')

        print(f'midtrans-sync: checked={checked} paid={paid} cancelled={cancelled} unchanged={unchanged} errors={errors}')

    return app