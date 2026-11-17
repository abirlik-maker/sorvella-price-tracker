"""Our own products and prices, from the shop's public /products.json (Shopify)."""
import json
import time
from pathlib import Path

import requests
from .util import parse_ml

BASE = "https://sorvellaperfume.pl"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/json", "Accept-Language": "pl-PL,pl;q=0.9"}
WAITS = (0, 20, 60)                 # the shop answers 429 when it thinks we ask too often
LAST = Path(__file__).resolve().parent.parent / "docs" / "data" / "latest.json"


def sized(src, width=200):
    """Ask the Shopify CDN for a small image."""
    if not src:
        return None
    return f'{src}{"&" if "?" in src else "?"}width={width}'


def image_for(product, variant):
    src = (variant.get("featured_image") or {}).get("src")
    if not src and product.get("images"):
        src = product["images"][0].get("src")
    return sized(src)


def _get(page):
    r = None
    for wait in WAITS:
        if wait:
            print(f"sorvellaperfume.pl said {r.status_code}, retrying in {wait}s", flush=True)
            time.sleep(wait)
        r = requests.get(f"{BASE}/products.json", params={"limit": 250, "page": page}, headers=HEADERS, timeout=30)
        if r.status_code not in (429, 502, 503):
            break
    r.raise_for_status()
    return r.json().get("products", [])


def _from_last_run():
    """Fallback: our product list and prices from the previous run."""
    d = json.loads(LAST.read_text(encoding="utf-8"))
    keep = ("id", "title", "size_ml", "our_price", "url", "image")
    out = [{k: p.get(k) for k in keep} for p in d["products"]]
    print(f"WARNING: could not read sorvellaperfume.pl, using our {len(out)} products and prices "
          f"from the previous run ({d['generated_at'][:10]})", flush=True)
    return out


def fetch_products(exclude_types=()):
    out, page = [], 1
    try:
        while True:
            items = _get(page)
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
                    out.append({
                        "id": f'{p["handle"]}-{v["id"]}' if multi else p["handle"],
                        "title": f'{p["title"]} {vt}'.strip(),
                        "size_ml": parse_ml(vt, p["title"]),
                        "our_price": float(v["price"]),
                        "url": f'{BASE}/products/{p["handle"]}',
                        "image": image_for(p, v),
                    })
            page += 1
    except requests.RequestException as e:
        if LAST.exists():
            print(f"sorvellaperfume.pl: {e}", flush=True)
            return _from_last_run()
        raise
    return out
