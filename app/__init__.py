"""Catering Batam - Flask Application Factory"""

import os
import logging
from logging.handlers import RotatingFileHandler
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

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Configure logging
    _configure_logging(app)

    # Template context processors
    @app.context_processor
    def utility_processor():
        def rp(n):
            return 'Rp ' + f'{n:,}'.replace(',', '.')
        return dict(rp=rp)

    return app