"""Daily run: python -m scraper.run"""
import json, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .sorvella import fetch_products
from .channels import all_channels, Blocked, Unreadable, Disabled
from .matching import match

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
DELAY = 1.0            # seconds between requests to one channel
MAX_FAILS = 3          # give up on a channel after this many failures in a row
CHANNEL_BUDGET = 150   # max seconds per channel


def log(*a):
    print(*a, flush=True)


def scrape_channel(c, products, ignore_urls):
    """Scrape one channel. Returns (channel_id, status, {product_id: offer})."""
    st = {"ok": 0, "fail": 0, "streak": 0, "state": "ok", "note": "", "cut": False}
    offers = {}
    start = time.monotonic()
    for i, p in enumerate(products):
        if st["state"] == "disabled" or st["streak"] >= MAX_FAILS:
            break
        if time.monotonic() - start > CHANNEL_BUDGET:
            st["cut"] = True
            st["note"] = f"time budget reached after {i}/{len(products)} products"
            break
        try:
            cands = c.search(p)
            st["ok"] += 1
            st["streak"] = 0
        except Disabled as e:
            st.update(state="disabled", note=str(e))
            break
        except (Blocked, Unreadable) as e:
            st["fail"] += 1
            st["streak"] += 1
            st["state"] = "blocked" if isinstance(e, Blocked) else "unreadable"
            st["note"] = str(e)
            time.sleep(DELAY)
            continue
        except Exception as e:  # network error etc.
            st["fail"] += 1
            st["streak"] += 1
            st["state"], st["note"] = "error", f"{type(e).__name__}: {e}"
            time.sleep(DELAY)
            continue
        best = None
        for cand in cands:
            if cand["url"] in ignore_urls:
                continue
            m = match(p, cand)
            if m and (best is None or cand["price"] < best["price"]):
                best = {"channel": c.id, **cand, "match": m["score"], "flag": m["flag"]}
        if best:
            offers[p["id"]] = best
        if (i + 1) % 10 == 0:
            log(f"[{c.id}] {i + 1}/{len(products)} products, {len(offers)} matches")
        time.sleep(DELAY)

    # final status
    if st["state"] != "disabled":
        if st["ok"] == 0 and st["fail"] > 0:
            pass  # keep last failure state
        elif st["fail"] > 0 or st["cut"]:
            st["state"] = "partial"
        else:
            st["state"] = "ok"
    log(f"[{c.id}] done: state={st['state']} ok={st['ok']} fail={st['fail']} matches={len(offers)}"
        + (f" note={st['note']}" if st["note"] else ""))
    return c.id, st, offers


def main():
    ov_path = ROOT / "overrides.json"
    overrides = json.loads(ov_path.read_text()) if ov_path.exists() else {}
    ignore_urls = set(overrides.get("ignore_urls", []))
    products = fetch_products(exclude_types=overrides.get("exclude_types", []))
    log(f"{len(products)} products from sorvellaperfume.pl")
    channels = all_channels()
    for p in products:
        p["offers"] = []

    with ThreadPoolExecutor(max_workers=len(channels)) as ex:
        results = list(ex.map(lambda c: scrape_channel(c, products, ignore_urls), channels))

    status = {}
    for cid, st, offers in results:
        status[cid] = st
        for p in products:
            if p["id"] in offers:
                p["offers"].append(offers[p["id"]])

    now = dt.datetime.now(dt.timezone.utc)
    latest = {
        "generated_at": now.isoformat(timespec="seconds"),
        "demo": False,
        "channels": [{"id": c.id, "name": c.name, "status": status[c.id]["state"],
                      "note": status[c.id]["note"]} for c in channels],
        "products": products,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=1))

    hist_path = DATA / "history.json"
    hist = json.loads(hist_path.read_text()) if hist_path.exists() else {}
    if hist.pop("_demo", None):
        hist = {}  # drop demo data
    day = now.date().isoformat()
    hist[day] = {p["id"]: {"own": p["our_price"], **{o["channel"]: o["price"] for o in p["offers"]}}
                 for p in products}
    for old in sorted(hist)[:-365]:
        del hist[old]
    hist_path.write_text(json.dumps(hist, ensure_ascii=False))
    log(f"{len(products)} products, {sum(len(p['offers']) for p in products)} matches")


if __name__ == "__main__":
    main()
