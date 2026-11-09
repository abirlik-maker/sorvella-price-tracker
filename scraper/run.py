"""Günlük çalıştırma: python -m scraper.run"""
import json, time, datetime as dt
from pathlib import Path
from .sorvella import fetch_products
from .channels import all_channels, Blocked, Unreadable, Disabled
from .matching import match

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
DELAY = 1.5          # istekler arası saniye
MAX_FAILS = 3        # art arda bu kadar hatadan sonra kanalı o gün bırak


def main():
    ov_path = ROOT / "overrides.json"
    overrides = json.loads(ov_path.read_text()) if ov_path.exists() else {}
    ignore_urls = set(overrides.get("ignore_urls", []))
    products = fetch_products(exclude_types=overrides.get("exclude_types", []))
    channels = all_channels()
    status = {c.id: {"ok": 0, "streak": 0, "state": "ok", "note": ""} for c in channels}
    for p in products:
        p["offers"] = []

    for c in channels:
        st = status[c.id]
        for p in products:
            if st["state"] == "disabled" or st["streak"] >= MAX_FAILS:
                break
            try:
                cands = c.search(p)
                st["ok"] += 1
                st["streak"] = 0
            except Disabled as e:
                st.update(state="disabled", note=str(e))
                break
            except (Blocked, Unreadable) as e:
                st["streak"] += 1
                st["state"] = "blocked" if isinstance(e, Blocked) else "unreadable"
                st["note"] = str(e)
                time.sleep(DELAY)
                continue
            except Exception as e:  # ağ hatası vb.
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
                p["offers"].append(best)
            time.sleep(DELAY)
        if st["ok"] and st["state"] != "disabled":
            st["state"] = "ok" if st["streak"] == 0 and not st["note"] else (
                "partial" if st["ok"] else st["state"])

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
        hist = {}  # demo verisini at
    day = now.date().isoformat()
    hist[day] = {p["id"]: {"own": p["our_price"], **{o["channel"]: o["price"] for o in p["offers"]}}
                 for p in products}
    for old in sorted(hist)[:-365]:
        del hist[old]
    hist_path.write_text(json.dumps(hist, ensure_ascii=False))
    print(f"{len(products)} ürün, {sum(len(p['offers']) for p in products)} eşleşme")


if __name__ == "__main__":
    main()
