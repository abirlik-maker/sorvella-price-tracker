"""Sorvella ürünlerini Shopify'ın herkese açık /products.json uç noktasından çeker."""
import requests
from .util import parse_ml

BASE = "https://sorvellaperfume.pl"
UA = "Mozilla/5.0 (compatible; SorvellaPriceBot/1.0)"


def sized(src, width=200):
    """Shopify CDN görselini küçük boyutta iste."""
    if not src:
        return None
    return f'{src}{"&" if "?" in src else "?"}width={width}'


def image_for(product, variant):
    src = (variant.get("featured_image") or {}).get("src")
    if not src and product.get("images"):
        src = product["images"][0].get("src")
    return sized(src)


def fetch_products(exclude_types=()):
    out, page = [], 1
    while True:
        r = requests.get(f"{BASE}/products.json", params={"limit": 250, "page": page},
                         headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        items = r.json().get("products", [])
        if not items:
            break
        for p in items:
            if p.get("product_type") in exclude_types:
                continue
            multi = len(p["variants"]) > 1
            for v in p["variants"]:
                if not v.get("available", True):
                    continue
                vt = v.get("title") if multi else ""
                title = f'{p["title"]} {vt}'.strip()
                out.append({
                    "id": f'{p["handle"]}-{v["id"]}' if multi else p["handle"],
                    "title": title,
                    "size_ml": parse_ml(vt, p["title"]),
                    "our_price": float(v["price"]),
                    "url": f'{BASE}/products/{p["handle"]}',
                    "image": image_for(p, v),
                })
        page += 1
    return out
