# Catering Batam — Storefront & Dashboard Admin

Toko online dan dashboard admin untuk Catering Batam (katering aqiqah & olahan kambing).
Dibangun dengan **Flask + Jinja + Tailwind CSS v4 + SQLAlchemy + Flask-Login + Flask-Migrate**.

## Tentang Aplikasi

- **Storefront pelanggan**: Jelajahi produk, tambah ke keranjang, checkout dengan Midtrans Snap, lihat riwayat dan status pesanan, unggah bukti pembayaran (legacy), beri ulasan produk.
- **Dashboard admin**: Kelola produk, kategori, tipe menu, pesanan, pelanggan, banner promo, ulasan, dan laporan transaksi (export Excel/PDF).
- **Keamanan**: Akses berbasis peran (customer/admin), proteksi CSRF, audit logging keamanan (JSON Lines untuk Wazuh SIEM), verifikasi email OTP saat registrasi.

## Kebutuhan

| Dependensi | Versi | Keterangan |
|---|---|---|
| Python | 3.10+ | Diuji di 3.14 |
| Node.js + npm | 18+ | Hanya untuk build Tailwind CSS |

Paket Python (lihat `requirements.txt`):
```bash
pip install -r requirements.txt
```

## Setup (Pengembangan)

**1. Buat virtualenv dan pasang dependensi:**
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Pasang dependensi Node (sekali saja):**
```bash
npm install
```

**3. Konfigurasi environment:**
```bash
cp .env.example .env
# Edit .env dengan kredensial database dan kunci Midtrans Anda
```

**4. Inisialisasi database:**
```bash
flask db upgrade
```

**5. Buat user admin (opsional):**
```bash
flask shell
>>> from app import db; from app.models import User
>>> admin = User(fullname='Admin', email='admin@cateringbatam.com', role='admin', email_verified=True)
>>> admin.set_password('admin123')
>>> db.session.add(admin); db.session.commit()
```

**6. Build CSS (jalankan di terminal kedua):**
```bash
npx @tailwindcss/cli -i input.css -o ./app/static/style/site.css --watch
```

**7. Jalankan Flask:**
```bash
python run.py
# Atau: flask --app app run --debug
```

Buka http://127.0.0.1:5000

## Variabel Environment

Lihat `.env.example` untuk semua variabel yang tersedia. Yang utama:

| Variabel | Deskripsi |
|---|---|
| `DATABASE_URL` | Connection string database (SQLite atau MySQL) |
| `SECRET_KEY` | Secret key Flask |
| `MAIL_SERVER` | Server SMTP untuk email OTP |
| `MAIL_PORT` | Port SMTP |
| `MAIL_USE_TLS` | Aktifkan STARTTLS |
| `MAIL_USERNAME` | Username SMTP |
| `MAIL_PASSWORD` | Password SMTP |
| `MAIL_DEFAULT_SENDER` | Alamat email pengirim |
| `MAIL_SUPPRESS_SEND` | Set `true` untuk skip pengiriman (mode dev) |
| `MIDTRANS_SERVER_KEY` | Server key Midtrans |
| `MIDTRANS_CLIENT_KEY` | Client key Midtrans |
| `MIDTRANS_IS_PRODUCTION` | Set `true` untuk production |

## Database

### Pengembangan (SQLite — default)
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

## Midtrans Sync (Cron)

Jalankan setiap 5 menit untuk sinkronisasi status pembayaran:
```cron
*/5 * * * * cd /path/to/app && .venv/bin/flask midtrans-sync
```

## Tailwind CSS

- `input.css` → source dengan token `@theme` + utilitas custom (`.batik-light`, `.mendung`)
- `static/style/site.css` → output hasil kompilasi (auto-generate via `--watch`)
- **Jangan edit `site.css` manual** — edit `input.css` lalu rebuild

## Security Audit Logging

- **Logger:** `app/security_logging.py` → logger `security_audit` (non-propagating)
- **Output:** `logs/security_audit.json` (JSON Lines, UTF-8)
- **Rotation:** 10 MB per file, 10 file backup
- **Events:** `admin_login_success`, `user_login_success`, `login_failed`, `user_logout`, `otp_sent`, `otp_verified`, `otp_failed`, `otp_locked`, `otp_resent`, `login_blocked_unverified`, `midtrans_payment_received`, `midtrans_signature_invalid`, `midtrans_amount_mismatch`, `midtrans_status_synced`
- **Schema (per baris):** `timestamp` (ISO 8601 UTC), `level`, `event`, `user_id`, `username`, `role`, `srcip`, `http_method`, `request_path`, `user_agent`, `status`, `reason`
- **Pemisahan:** Log aplikasi (`catering_batam.log`) dan audit log keamanan benar-benar terpisah

## Design System

| Token | Nilai | Penggunaan |
|---|---|---|
| `--color-maroon` | `#a73121` | Brand utama, tombol, teks |
| `--color-maroon-dark` | `#8a2618` | Hover, border |
| `--color-cream` | `#f2e8c6` | Background card, section |
| `--color-gold` | `#f59e0b` | Aksen, badge, highlight |
| `--color-paper` | `#fffdf4` | Baris tabel, stat card |
| `--color-ink` | `#2b1a12` | Teks body |

**Font:** Salsa (judul), Comic Neue (body), Julius Sans One (logo)

**Pola:** `.batik-light` (batik kawung), `.mendung` (mega mendung)

## Struktur Proyek

```text
app/
├── __init__.py          # create_app(), extensions, blueprints
├── models.py            # Semua model (User, Product, Order, dll)
├── security_logging.py  # Security audit logger
├── auth/                # login, register, logout, verifikasi OTP
├── main/                # halaman storefront, cart, checkout, order
├── admin/               # dashboard admin, produk, pesanan, pelanggan, laporan
├── payments.py          # Utilitas sync Midtrans
├── templates/           # Template Jinja
└── static/              # CSS, JS, gambar
run.py                   # Entry point
migrations/              # Migrasi Alembic
input.css                # Source Tailwind
logs/                    # Runtime logs (gitignored)
uploads/                 # Upload bukti pembayaran (gitignored)
```