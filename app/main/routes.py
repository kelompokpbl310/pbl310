"""Main Routes - Public Pages"""

from flask import render_template, url_for
from app.main import bp
from app import db
from app.models import Product


# Promo slides data (static for now)
PROMO_SLIDES = [
    dict(badge='TERLARIS', headline='Nasi Kebuli Kambing',
         subtitle='Menu favorit pelanggan aqiqah. Bumbu rempah, daging empuk.',
         price=40000, unit='/box', cta='Pesan Sekarang',
         cta_endpoint='main.detail_produk', img='img/assets2.png',
         alt='Nasi kebuli kambing dengan lauk, menu aqiqah terlaris'),
    dict(badge='HEMAT', headline='Paket Aqiqah Hemat',
         subtitle='Pas untuk syukuran sederhana, tetap lezat dan berkesan.',
         price=38000, unit='', cta='Pesan Sekarang',
         cta_endpoint='main.detail_produk', img='img/banners/paket-hemat.png',
         alt='Paket aqiqah hemat untuk syukuran sederhana'),
    dict(badge='LENGKAP', headline='Paket Aqiqah Lengkap',
         subtitle='Dimasak, dikemas, dan diantar. Anak laki-laki 2 ekor, perempuan 1 ekor.',
         price=2750000, unit='', cta='Lihat Paket',
         cta_endpoint='main.produk', cta_anchor='katalog',
         img='img/banners/paket-lengkap.png',
         alt='Paket aqiqah lengkap dengan layanan antar'),
    dict(badge='FAVORIT', headline='Sate Kambing Empuk',
         subtitle='Daging empuk bumbu kacang, dibakar arang kelapa.',
         price=38000, unit='/10 tusuk', cta='Pesan Sekarang',
         cta_endpoint='main.detail_produk', img='img/assets4.png',
         alt='Sate kambing empuk dengan bumbu kacang'),
    dict(badge='SPESIAL', headline='Kambing Guling Utuh',
         subtitle='Panggang utuh untuk pesta dan syukuran besar.',
         price=2450000, unit='/ekor', cta='Pesan Sekarang',
         cta_endpoint='main.detail_produk', img='img/assets1.png',
         alt='Kambing guling utuh siap saji'),
]


@bp.route('/')
def index():
    return render_template('index.html')


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
    return render_template('produk.html', promo_slides=slides)


@bp.route('/detail-produk')
def detail_produk():
    return render_template('detail-produk.html')


@bp.route('/checkout')
def checkout():
    return render_template('checkout.html')


@bp.route('/tentang')
def tentang():
    return render_template('tentang.html')