"""Builds a single-file demo on sample data: python make_demo.py
Competitor prices are SAMPLES. Sorvella names, prices and image URLs are the real values from the site."""
import json, random, datetime as dt
from pathlib import Path

ROOT = Path(__file__).parent
random.seed(7)
today = dt.date(2026, 11, 9)

CDN = "https://sorvellaperfume.pl/cdn/shop/files/"
IMAGES = {
    "amber-saffron": CDN + "13_3f8fe228-0085-4f88-ab3e-34c61061adf9.png?v=1793949773",
    "tobacco-honey-perfumy-unisex-sorvella": CDN + "17_8b572a9c-7a96-40b6-b8f8-6acce6e542fb.png?v=1793950724",
    "pear-musk-perfumy-unisex-sorvella-copy": CDN + "18_e322487f-7ef3-4a60-8a93-bbfe8a4b42d6.png?v=1793950766",
    "sandalwood-zapach-domowy-premium-120ml": CDN + "Strona_Packshoty_709_6.png?v=1789649822",
    "zapach-domowy-sorvella-istanbul-120-ml": CDN + "61.png?v=1789649069",
}

products = [
    ("amber-saffron", "Amber & Saffron - Perfumy Unisex Sorvella Signature 30ml", 30, 119.90),
    ("tobacco-honey-perfumy-unisex-sorvella", "Tobacco & Honey- Perfumy Unisex Sorvella Signature 30ml", 30, 119.90),
    ("pear-musk-perfumy-unisex-sorvella-copy", "Pear & Musk- Perfumy Unisex Sorvella Signature 30ml", 30, 119.90),
    ("sandalwood-zapach-domowy-premium-120ml", "Sandalwood - Zapach Domowy Sorvella 120ml", 120, 49.90),
    ("zapach-domowy-sorvella-istanbul-120-ml", "Istanbul - Zapach Domowy Sorvella - 120 Ml", 120, 49.90),
]
# id -> {channel: (price, match, check)}
sample = {
    "amber-saffron": {"allegro": (109.00, 100, False), "ceneo": (114.99, 96, False)},
    "tobacco-honey-perfumy-unisex-sorvella": {"allegro": (119.90, 100, False), "ceneo": (127.00, 88, True)},
    "pear-musk-perfumy-unisex-sorvella-copy": {},
    "sandalwood-zapach-domowy-premium-120ml": {"allegro": (44.90, 97, False)},
    "zapach-domowy-sorvella-istanbul-120-ml": {"allegro": (52.00, 100, False)},
}
channels = [
    {"id": "allegro", "name": "Allegro", "status": "ok", "note": ""},
    {"id": "ceneo", "name": "Ceneo", "status": "ok", "note": ""},
    {"id": "notino", "name": "Notino", "status": "blocked", "note": "HTTP 403"},
    {"id": "douglas", "name": "Douglas", "status": "unreadable", "note": "results page unreadable (probably rendered with JavaScript)"},
    {"id": "sephora", "name": "Sephora", "status": "ok", "note": ""},
    {"id": "rossmann", "name": "Rossmann", "status": "ok", "note": ""},
    {"id": "hebe", "name": "Hebe", "status": "ok", "note": ""},
    {"id": "superpharm", "name": "Super-Pharm", "status": "ok", "note": ""},
]
latest = {"generated_at": "2026-11-09T06:00:00+00:00", "demo": True, "channels": channels, "products": []}
for pid, title, ml, price in products:
    offers = [{"channel": ch, "title": title.replace("Perfumy Unisex ", ""), "price": v[0],
               "url": f"https://example.com/{ch}/{pid}", "match": v[1], "flag": v[2]}
              for ch, v in sample[pid].items()]
    latest["products"].append({"id": pid, "title": title, "size_ml": ml, "our_price": price,
                               "url": f"https://sorvellaperfume.pl/products/{pid}",
                               "image": IMAGES[pid] + "&width=200", "offers": offers})

hist = {}
for back in range(29, -1, -1):
    d = (today - dt.timedelta(days=back)).isoformat()
    hist[d] = {}
    for p in latest["products"]:
        row = {"own": p["our_price"]}
        for o in p["offers"]:
            drift = random.choice([-1, 0, 0, 1]) * random.choice([0, 1.0, 2.0, 3.0]) * (back / 29)
            row[o["channel"]] = round(o["price"] + drift, 2)
        hist[d][p["id"]] = row
hist[today.isoformat()] = {p["id"]: {"own": p["our_price"], **{o["channel"]: o["price"] for o in p["offers"]}} for p in latest["products"]}

# also store as the repo's first data (the first real run overwrites it)
(ROOT / "docs/data/latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=1))
(ROOT / "docs/data/history.json").write_text(json.dumps({"_demo": True, **hist}, ensure_ascii=False))

html = (ROOT / "docs/index.html").read_text()
blob = json.dumps({"latest": latest, "history": hist}, ensure_ascii=False).replace("</", "<\\/")
html = html.replace("<!--INLINE_DATA-->", f'<script id="inline-data" type="application/json">{blob}</script>')
(ROOT / "demo.html").write_text(html)
print("demo.html written")
