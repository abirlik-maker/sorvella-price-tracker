"""Competitor sellers on Allegro, from Base.com (BaseLinker) competition monitoring.

    python -m scraper.base            read Base and write docs/data/base_competitors.json
    python -m scraper.base --apply    only attach the saved file to docs/data/latest.json

Base has no API for competitor data, so this reads the Base panel in a Chrome window that
remembers your login (PROFILE_DIR). The first time, log in to Base in that window yourself.
"""
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
FILE = DATA / "base_competitors.json"
PANEL = os.getenv("BASE_PANEL", "https://panel-d.baselinker.com")
OWN_LOGIN = "sorvella"
OWN_LABELS = {OWN_LOGIN, "moja oferta"}   # Base shows our own listing as "Moja oferta"
MAX_AGE_DAYS = 8

# Runs in the Base panel page: lists our active Allegro offers, then reads the competition
# tab of each offer. Verified on the live panel on 17 Nov 2026.
EXTRACT_JS = r"""async () => {
  const num = s => { const m = /(-?\d+(?:[.,]\d+)?)\s*PLN/.exec((s || '').replace(/ /g, ' ')); return m ? parseFloat(m[1].replace(',', '.')) : null; };
  const plain = s => { const m = /(\d+(?:[.,]\d+)?)/.exec((s || '').replace(/\s/g, '')); return m ? parseFloat(m[1].replace(',', '.')) : null; };
  const r0 = await fetch('/allegro_auctions.php?status_id=1&limit=500', {credentials: 'include'});
  const listDoc = new DOMParser().parseFromString(await r0.text(), 'text/html');
  const offers = [...listDoc.querySelectorAll('tr[id^="a_"]')].map(tr => {
    const tds = [...tr.querySelectorAll('td')];
    const cell = tds.find(td => /SORVELLA/i.test(td.textContent)) || tds[2] || tr;
    const t = (cell.textContent || '').replace(/\s+/g, ' ').trim();
    const input = tr.querySelector('input[name*="price" i], input[value*="."]');
    const priceText = tds.map(td => td.textContent).find(x => /PLN/.test(x)) || '';
    return {bl_id: tr.id.slice(2), allegro_offer: (t.match(/\((\d{9,})\)/) || [])[1] || null,
            ean: (t.match(/EAN\s*(\d{8,14})/) || [])[1] || null, sku: (t.match(/SKU\s*([\w-]+)/) || [])[1] || null,
            title: t.replace(/\(\d{9,}\).*$/, '').trim().slice(0, 160), price: input ? plain(input.value) : plain(priceText)};
  });
  for (const o of offers) {
    try {
      const r = await fetch(`/ajax/modal/modal_allegro_auction_details.php?id=${o.bl_id}&autoSelectTab=auction_modal_reprice`, {credentials: 'include'});
      const d = new DOMParser().parseFromString(await r.text(), 'text/html');
      const tbl = [...d.querySelectorAll('table')].find(t => /Login/i.test(t.textContent) && /Suma/i.test(t.textContent));
      const rows = tbl ? [...tbl.querySelectorAll('tr')].slice(1).map(tr => { const cells = [...tr.children].map(c => c.textContent.replace(/\s+/g, ' ').trim());
        const a = tr.children[1] && tr.children[1].querySelector('a[href]'); cells.url = a ? a.href : null; return cells; }) : [];
      o.monitoring = /Monitorowanie konkurencji[\s\S]{0,200}?Włączone/.test(d.body.textContent);
      o.competitors = rows.filter(c => c.length >= 6 && c[0]).map(c => ({login: c[0], title: c[1].slice(0, 100), sold30: c[2], price: num(c[3]), ship: num(c[4]), total: num(c[5]), url: c.url}));
    } catch (e) { o.competitors = []; o.error = String(e).slice(0, 80); }
    await new Promise(res => setTimeout(res, 350));
  }
  return offers;
}"""


def fetch():
    from playwright.sync_api import sync_playwright
    profile = Path(os.getenv("PROFILE_DIR") or Path.home() / ".sorvella-profile") / "base"
    wait = int(os.getenv("BASE_LOGIN_WAIT", "600"))
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(profile), headless=False, channel=os.getenv("BROWSER_CHANNEL") or None,
            args=["--disable-blink-features=AutomationControlled"], ignore_default_args=["--enable-automation"],
            locale="pl-PL", viewport={"width": 1366, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{PANEL}/allegro_auctions.php?status_id=1", wait_until="domcontentloaded", timeout=60000)
        logged_in = lambda: page.locator('tr[id^="a_"]').count() > 0
        page.wait_for_timeout(2500)
        if not logged_in():
            print(f"[base] Log in to Base in the Chrome window (waiting up to {wait // 60} minutes)...", flush=True)
            end = time.monotonic() + wait
            while time.monotonic() < end and not logged_in():
                page.wait_for_timeout(3000)
                if "allegro_auctions" not in page.url and "login" not in page.url.lower():
                    try:   # after login Base may land on the dashboard: go back to the offers page
                        page.goto(f"{PANEL}/allegro_auctions.php?status_id=1", wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(2500)
                    except Exception:
                        pass
            if not logged_in():
                raise RuntimeError("not logged in to Base")
        print("[base] reading our Allegro offers and their competitors...", flush=True)
        offers = page.evaluate(EXTRACT_JS)
    for o in offers:
        o["competitors"] = [c for c in o.get("competitors", []) if c["login"].strip().lower() not in OWN_LABELS]
    data = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "source": "Base.com competition monitoring (Allegro)", "offers": offers}
    DATA.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False))
    n = sum(len(o["competitors"]) for o in offers)
    print(f"[base] {len(offers)} of our Allegro offers, {n} competitor listings, "
          f"{len({c['login'] for o in offers for c in o['competitors']})} sellers", flush=True)


def load():
    """The saved Base file, if it is recent enough to use."""
    if not FILE.exists():
        return None
    d = json.loads(FILE.read_text(encoding="utf-8"))
    age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(d["generated_at"])
    if age.days > MAX_AGE_DAYS:
        print(f"[base] saved Base data is {age.days} days old, not used", flush=True)
        return None
    return d


def own_offer_ids(d):
    return {o["allegro_offer"] for o in (d or {}).get("offers", []) if o.get("allegro_offer")}


def attach(products, d):
    """Give each of our products its Allegro listing (price) and the competitor sellers from Base."""
    from .matching import match
    if not d:
        return 0
    n = 0
    for o in d["offers"]:
        best = None
        for p in products:
            m = match(p, {"title": o["title"]})
            if m and (best is None or m["score"] > best[1]):
                best = (p, m["score"])
        if not best:
            continue
        p = best[0]
        if "base" in p and p["base"]["price"] <= o["price"]:
            continue                       # two of our listings for one product: keep the cheaper one
        sellers = sorted((c for c in o["competitors"] if c.get("price") and c["login"].strip().lower() not in OWN_LABELS), key=lambda c: c["price"])
        p["base"] = {"allegro_offer": o["allegro_offer"], "price": o["price"], "monitoring": o.get("monitoring"),
                     "sellers": sellers, "as_of": d["generated_at"]}
        p["own_allegro"] = {"price": o["price"], "url": f"https://allegro.pl/oferta/{o['allegro_offer']}", "title": o["title"]}
        if sellers:   # Base sees more Allegro sellers than the search page: use its cheapest when it is lower
            c = sellers[0]
            al = next((x for x in p.get("offers", []) if x["channel"] == "allegro"), None)
            if al is None or c["price"] < al["price"] - 0.005:
                p["offers"] = [x for x in p.get("offers", []) if x["channel"] != "allegro"] + [{
                    "channel": "allegro", "title": c["title"], "price": c["price"], "seller": c["login"], "source": "base",
                    "url": c.get("url") or f"https://allegro.pl/uzytkownik/{c['login']}", "match": 100, "flag": False}]
        n += 1
    print(f"[base] attached Base sellers to {n} of our products", flush=True)
    return n


def apply_to_latest():
    latest = DATA / "latest.json"
    d = json.loads(latest.read_text(encoding="utf-8"))
    b = load()
    attach(d["products"], b)
    d["base"] = {"as_of": b["generated_at"]} if b else None
    latest.write_text(json.dumps(d, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if "--apply" in sys.argv:
        apply_to_latest()
        sys.exit(0)
    code = 0
    try:
        fetch()
    except Exception as e:
        print(f"[base] skipped: {type(e).__name__}: {e}", flush=True)
        code = 1
    sys.stdout.flush()
    os._exit(code)                 # do not wait for the browser to close (it can hang on macOS)
