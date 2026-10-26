"""Shared helpers for main blueprint routes."""

from flask import current_app
from app import db
from app.models import Product
from PIL import Image
import os
import uuid


def build_cart_summary(user_id):
    """Build cart summary for a given user. Returns (cart_items, cart_subtotal, cart_total)."""
    from app.models import CartItem

    cart_items_db = CartItem.query.filter_by(user_id=user_id).join(Product).filter(Product.is_active == True).all()
    cart_items = []
    cart_subtotal = 0

    for item in cart_items_db:
        product = item.product
        qty = item.quantity
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

    return cart_items, cart_subtotal, cart_total


def normalize_image_to_rgb(img):
    """Convert image to RGB mode, handling RGBA/LA/P modes."""
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    return img