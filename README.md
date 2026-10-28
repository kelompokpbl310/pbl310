# Catering Batam — Front-End + Backend

Storefront & dashboard admin Catering Batam (katering aqiqah & kambing)
dibangun dengan **Flask + Jinja + Tailwind CSS v4 + SQLAlchemy + Flask-Login + Flask-Migrate**.

## Status Saat Ini

✅ **Phase 1: Backend Foundation (SELESAI)**
- SQLite untuk development, MySQL ready untuk production
- Models: User, Category, Product, Order, OrderItem, Review, Setting
- Auth: Flask-Login (session-based), role-based access (customer/admin)
- Migrations: Flask-Migrate (Alembic) configured
- Blueprint structure: `main`, `auth`, `admin`, `api`

✅ **Security Audit Logging (SELESAI)**
- Dedicated security logger: `app/security_logging.py`
- JSON Lines output to `logs/security_audit.json` (rotating 10MB, 10 backups)
- Events: `admin_login_success`, `user_login_success`, `login_failed`, `user_logout`
- Separate from application log (`logs/catering_batam.log`)
- Wazuh SIEM-ready schema (ISO 8601 UTC timestamps, `srcip` field, stable event names)

## Kebutuhan

| Perangkat | Versi | Keterangan |
| --- | --- | --- |
| Python | 3.10+ | Teruji di 3.14 |
| Node.js + npm | Node 18+ | Hanya untuk membangun CSS Tailwind |

Paket Python:
```bash
pip install flask flask-sqlalchemy flask-login flask-migrate python-dotenv pymysql
```

## Menjalankan (Pengembangan)

**1. Buat & aktifkan virtualenv, pasang dependensi Python:**

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install flask flask-sqlalchemy flask-login flask-migrate python-dotenv pymysql
```

**2. Pasang dependensi Node (sekali saja):**

```bash
npm install
```

**3. Setup environment (copy .env.example ke .env lalu edit):**

```bash
cp .env.example .env
# Edit .env dengan kredensial database Anda
```

**4. Inisialisasi database (sekali saja):**

```bash
flask db upgrade
# Atau jika baru pertama kali:
flask db init
flask db migrate -m "Initial schema"
flask db upgrade
```

**5. Buat user admin (opsional):**

```bash
flask shell
>>> from app import db; from app.models import User
>>> admin = User(fullname='Admin', email='admin@cateringbatam.com', role='admin')
>>> admin.set_password('admin123')
>>> db.session.add(admin); db.session.commit()
```

**6. Bangun CSS (biarkan berjalan di terminal kedua):**

```bash
npx @tailwindcss/cli -i input.css -o ./app/static/style/site.css --watch
```

**7. Jalankan Flask (di terminal pertama, venv aktif):**

```bash
python run.py
# Atau: flask --app app run --debug
```

Buka http://127.0.0.1:5000

## Daftar Rute (Blueprint Prefixes)

### Public (main)
| URL | Endpoint | Halaman |
| --- | --- | --- |
| `/` | `main.index` | Beranda |
| `/produk` | `main.produk` | Katalog + peta potongan kambing |
| `/detail-produk` | `main.detail_produk` | Detail paket |
| `/checkout` | `main.checkout` | Checkout |
| `/tentang` | `main.tentang` | Tentang Kami |

### Auth
| URL | Endpoint | Halaman |
| --- | --- | --- |
| `/auth/login` | `auth.login` | Login (POST → redirect by role) |
| `/auth/register` | `auth.register` | Register (POST → create user) |
| `/auth/logout` | `auth.logout` | Logout |

### Admin (prefix `/admin`, `@login_required` + `@admin_required`)
| URL | Endpoint | Halaman |
| --- | --- | --- |
| `/admin/dashboard` | `admin.dashboard` | Ringkasan |
| `/admin/pesanan` | `admin.pesanan` | Pesanan + alur aqiqah |
| `/admin/produk` | `admin.produk` | Produk & paket (CRUD) |
| `/admin/pelanggan` | `admin.pelanggan` | Pelanggan |
| `/admin/laporan` | `admin.laporan` | Laporan |
| `/admin/ulasan` | `admin.ulasan` | Ulasan |
| `/admin/pengaturan` | `admin.pengaturan` | Pengaturan toko |

**Test Credentials:**
- Admin: `admin@cateringbatam.com` / `admin123`
- Customer: register via `/auth/register`

## Struktur Proyek

```text
app/
├── __init__.py          # create_app(), extensions (db, login, migrate), blueprints
├── models.py            # Semua models (User, Product, Order, dll)
├── security_logging.py  # Security audit logger (JSON Lines → logs/security_audit.json)
├── auth/
│   ├── __init__.py
│   └── routes.py        # login, register, logout
├── main/
│   ├── __init__.py
│   └── routes.py        # index, produk, detail, checkout, tentang
├── admin/
│   ├── __init__.py
│   └── routes.py        # dashboard, pesanan, produk, pelanggan, laporan, ulasan, pengaturan
├── api/                 # (kosong, siap untuk API future)
├── templates/           # Semua template Jinja (di dalam app/)
│   ├── base.html        # Layout utama (header, footer, nav)
│   ├── index.html       # Beranda
│   ├── produk.html      # Katalog produk
│   ├── detail-produk.html   # Detail produk + related
│   ├── checkout.html    # Checkout form
│   ├── login.html       # Login form
│   ├── register.html    # Register form
│   ├── tentang.html     # Tentang kami
│   └── dashboard/
│       ├── base.html    # Layout admin (sidebar, header)
│       ├── ringkasan.html   # Dashboard ringkasan
│       ├── pesanan.html     # Daftar pesanan
│       ├── produk.html      # CRUD produk
│       ├── pelanggan.html   # Daftar pelanggan
│       ├── laporan.html     # Laporan penjualan
│       ├── ulasan.html      # Ulasan produk
│       └── pengaturan.html  # Pengaturan toko
└── static/              # Static files (di dalam app/)
    ├── style/site.css       # CSS hasil kompilasi Tailwind (jangan edit manual)
    ├── script/site.js       # Carousel, tabs, qty, goat-cut map
    └── script/dashboard.js  # Dashboard interactions
    └── img/                 # Gambar (banners, assets)
run.py                   # Entry point: app = create_app()
migrations/              # Alembic migrations
input.css                # Token Tailwind v4 + utilitas batik/mendung
.env                     # Environment variables (DATABASE_URL, SECRET_KEY)
PROGRESS.md              # Progress log per phase
logs/                    # Runtime logs (gitignored): security_audit.json, catering_batam.log
```

## Database

### Development (SQLite - default)
```env
DATABASE_URL=sqlite:///catering_batam.db
```

### Production (MySQL)
```env
DATABASE_URL=mysql+pymysql://flask_user:password@host/dbname
```

Lalu jalankan:
```bash
flask db upgrade
```

## Tailwind CSS

- `input.css` → source dengan `@theme` tokens + custom utilities (`.batik-light`, `.mendung`)
- `static/style/site.css` → compiled output (auto-generated via `--watch`)
- **Jangan edit `site.css` manual** — edit `input.css` lalu rebuild

## Security Audit Logging

- **Logger:** `app/security_logging.py` → `security_audit` logger (non-propagating)
- **Output:** `logs/security_audit.json` (JSON Lines, UTF-8)
- **Rotation:** 10 MB per file, 10 backup files
- **Events:**
  | Event | Level | Description |
  | --- | --- | --- |
  | `admin_login_success` | INFO | Admin login berhasil |
  | `user_login_success` | INFO | User biasa login berhasil |
  | `login_failed` | WARNING | Login gagal (reason: `invalid_credentials` / `user_not_found`) |
  | `user_logout` | INFO | Logout berhasil (admin/user) |
- **Schema (per line):** `timestamp` (ISO 8601 UTC), `level`, `event`, `user_id`, `username`, `role`, `srcip`, `http_method`, `request_path`, `user_agent`, `status`, `reason`
- **Separation:** Application logs (`catering_batam.log`) and security audit logs are completely separate
- **Wazuh-ready:** Stable event names, consistent fields, no sensitive data

## Design System

| Token | Value | Usage |
| --- | --- | --- |
| `--color-maroon` | `#a73121` | Primary brand, buttons, text |
| `--color-maroon-dark` | `#8a2618` | Hover states, borders |
| `--color-cream` | `#f2e8c6` | Background cards, sections |
| `--color-gold` | `#f59e0b` | Accent, badges, highlights |
| `--color-paper` | `#fffdf4` | Table rows, stat cards |
| `--color-ink` | `#2b1a12` | Body text |

**Fonts:**
- `Salsa` — Titles, headings, buttons
- `Comic Neue` — Body text, paragraphs, small text
- `Julius Sans One` — Logo

**Patterns:**
- `.batik-light` — Batik kawung (cream surfaces, explicit only)
- `.mendung` / `.bg-maroon` / `.bg-maroon-dark` — Mega mendung cloud waves (red surfaces)

## Midtrans Sync (Cron)

Jalankan perintah berikut setiap 5 menit untuk sinkronisasi status pembayaran Midtrans:

```cron
*/5 * * * * cd /path/to/app && .venv/bin/flask midtrans-sync
```

## Next: Phase 2 - Admin CRUD

Prioritas:
1. **Produk CRUD** — List, Create, Edit, Delete (soft delete `is_active`)
2. **Orders** — List, Detail, Update status
3. **Categories** — CRUD
4. **Image upload** — Produk images

Lihat `PROGRESS.md` untuk detail progres tiap phase.