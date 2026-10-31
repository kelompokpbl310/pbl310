# Catering Batam — Storefront & Admin Dashboard

Aqiqah catering storefront and admin dashboard for Catering Batam (goat dishes and aqiqah packages).
Built with **Flask + Jinja + Tailwind CSS v4 + SQLAlchemy + Flask-Login + Flask-Migrate**.

## What This App Does

- **Customer storefront**: Browse products, add to cart, checkout with Midtrans Snap payment, view order history and status, upload payment proof (legacy), leave product reviews.
- **Admin dashboard**: Manage products, categories, menu types, orders, customers, promo banners, reviews, and transaction reports (Excel/PDF export).
- **Security**: Role-based access (customer/admin), CSRF protection, security audit logging (JSON Lines for Wazuh SIEM), email OTP verification on registration.

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.10+ | Tested on 3.14 |
| Node.js + npm | 18+ | Only for building Tailwind CSS |

Python packages (see `requirements.txt`):
```bash
pip install -r requirements.txt
```

## Setup (Development)

**1. Create virtualenv and install dependencies:**
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Install Node dependencies (once):**
```bash
npm install
```

**3. Configure environment:**
```bash
cp .env.example .env
# Edit .env with your database credentials and Midtrans keys
```

**4. Initialize database:**
```bash
flask db upgrade
```

**5. Create admin user (optional):**
```bash
flask shell
>>> from app import db; from app.models import User
>>> admin = User(fullname='Admin', email='admin@cateringbatam.com', role='admin', email_verified=True)
>>> admin.set_password('admin123')
>>> db.session.add(admin); db.session.commit()
```

**6. Build CSS (run in a second terminal):**
```bash
npx @tailwindcss/cli -i input.css -o ./app/static/style/site.css --watch
```

**7. Run Flask:**
```bash
python run.py
# Or: flask --app app run --debug
```

Open http://127.0.0.1:5000

## Environment Variables

See `.env.example` for all available variables. Key ones:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Database connection string (SQLite or MySQL) |
| `SECRET_KEY` | Flask secret key |
| `MAIL_SERVER` | SMTP server for OTP emails |
| `MAIL_PORT` | SMTP port |
| `MAIL_USE_TLS` | Enable STARTTLS |
| `MAIL_USERNAME` | SMTP username |
| `MAIL_PASSWORD` | SMTP password |
| `MAIL_DEFAULT_SENDER` | Sender email address |
| `MAIL_SUPPRESS_SEND` | Set `true` to skip sending (dev mode) |
| `MIDTRANS_SERVER_KEY` | Midtrans server key |
| `MIDTRANS_CLIENT_KEY` | Midtrans client key |
| `MIDTRANS_IS_PRODUCTION` | Set `true` for production |

## Database

### Development (SQLite — default)
```env
DATABASE_URL=sqlite:///catering_batam.db
```

### Production (MySQL)
```env
DATABASE_URL=mysql+pymysql://flask_user:password@host/dbname
```

Then run:
```bash
flask db upgrade
```

## Midtrans Sync (Cron)

Run every 5 minutes to sync payment statuses:
```cron
*/5 * * * * cd /path/to/app && .venv/bin/flask midtrans-sync
```

## Tailwind CSS

- `input.css` → source with `@theme` tokens + custom utilities (`.batik-light`, `.mendung`)
- `static/style/site.css` → compiled output (auto-generated via `--watch`)
- **Do not edit `site.css` manually** — edit `input.css` then rebuild

## Security Audit Logging

- **Logger:** `app/security_logging.py` → `security_audit` logger (non-propagating)
- **Output:** `logs/security_audit.json` (JSON Lines, UTF-8)
- **Rotation:** 10 MB per file, 10 backup files
- **Events:** `admin_login_success`, `user_login_success`, `login_failed`, `user_logout`, `otp_sent`, `otp_verified`, `otp_failed`, `otp_locked`, `otp_resent`, `login_blocked_unverified`, `midtrans_payment_received`, `midtrans_signature_invalid`, `midtrans_amount_mismatch`, `midtrans_status_synced`
- **Schema (per line):** `timestamp` (ISO 8601 UTC), `level`, `event`, `user_id`, `username`, `role`, `srcip`, `http_method`, `request_path`, `user_agent`, `status`, `reason`
- **Separation:** Application logs (`catering_batam.log`) and security audit logs are completely separate

## Design System

| Token | Value | Usage |
|---|---|---|
| `--color-maroon` | `#a73121` | Primary brand, buttons, text |
| `--color-maroon-dark` | `#8a2618` | Hover states, borders |
| `--color-cream` | `#f2e8c6` | Background cards, sections |
| `--color-gold` | `#f59e0b` | Accent, badges, highlights |
| `--color-paper` | `#fffdf4` | Table rows, stat cards |
| `--color-ink` | `#2b1a12` | Body text |

**Fonts:** Salsa (titles), Comic Neue (body), Julius Sans One (logo)

**Patterns:** `.batik-light` (batik kawung), `.mendung` (mega mendung cloud waves)

## Project Structure

```text
app/
├── __init__.py          # create_app(), extensions, blueprints
├── models.py            # All models (User, Product, Order, etc.)
├── security_logging.py  # Security audit logger
├── auth/                # login, register, logout, OTP verification
├── main/                # storefront pages, cart, checkout, orders
├── admin/               # admin dashboard, products, orders, customers, reports
├── payments.py          # Midtrans sync utilities
├── templates/           # Jinja templates
└── static/              # CSS, JS, images
run.py                   # Entry point
migrations/              # Alembic migrations
input.css                # Tailwind source
logs/                    # Runtime logs (gitignored)
uploads/                 # Payment proof uploads (gitignored)
```