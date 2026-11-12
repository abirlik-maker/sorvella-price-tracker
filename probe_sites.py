"""Do these shops sell Sorvella, and can we read their search pages?

Run on your own computer, same setup as run_local.py:
    source .venv/bin/activate
    python probe_sites.py
A Chrome window opens and visits each shop's search page for "sorvella".
If a shop shows a human check, solve it in the window. Nothing is sent anywhere:
the report stays in ~/sorvella-probe (screenshots + report.json).
"""
import json
import os
import time
from pathlib import Path

from scraper.browser import EXTRACT_JS, BOT_WORDS

SITES = {
    "hebe": ["https://www.hebe.pl/search?q=sorvella"],
    "rossmann": ["https://www.rossmann.pl/szukaj?Query=sorvella"],
}
# Set aside for now: notino (wait page), douglas (no results), biedronka / sephora / superpharm (no working search URL).


def look(page, status):
    title = (page.title() or "")
    body = page.inner_text("body")
    low = body.lower()
    bot = status in (403, 429, 503) or any(w in title.lower() for w in BOT_WORDS) or (
        len(body) < 2500 and any(w in low for w in BOT_WORDS))
    items = [] if bot else page.evaluate(EXTRACT_JS)
    return {"status": status, "final_url": page.url.split("?")[0], "title": title[:70], "chars": len(body),
            "mentions": low.count("sorvella"), "bot_check": bot, "items": len(items),
            "examples": [f'{i["title"][:60]} = {i["price"]}' for i in items[:5]],
            "snippet": " ".join(body.split())[:160]}


def verdict(r):
    if r["bot_check"]:
        return "BLOCKED by a bot check"
    if r["status"] in (404, 410) or (r["chars"] < 400):
        return "wrong URL or empty page"
    if r["items"]:
        return "READABLE - can be added"
    if r["mentions"] > 2:
        return "Sorvella is on the page but the product cards are not readable (needs a custom reader)"
    if r["mentions"]:
        return "no products (the only mention is the search word itself)"
    return "no Sorvella found (not sold there, or the page did not render)"


def probe(sites, out_dir, wait_human=60):
    from playwright.sync_api import sync_playwright
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    headless = os.getenv("HEADLESS", "0") == "1"
    profile = Path(os.getenv("PROFILE_DIR", str(Path.home() / ".sorvella-profile"))) / "probe"
    report = {}
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(profile), headless=headless, channel=os.getenv("BROWSER_CHANNEL") or None,
            args=["--disable-blink-features=AutomationControlled"], ignore_default_args=["--enable-automation"],
            locale="pl-PL", timezone_id="Europe/Warsaw", viewport={"width": 1366, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for site, urls in sites.items():
            best = None
            for i, url in enumerate(urls):
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=12000)
                    except Exception:
                        pass
                    end = time.monotonic() + 30          # "Cierpliwosci..." / "Just a moment" pages clear by themselves
                    while time.monotonic() < end and any(w in (page.title() or "").lower() for w in ("cierpliwo", "just a moment", "please wait")):
                        page.wait_for_timeout(2000)
                    page.wait_for_timeout(2500)
                    r = look(page, resp.status if resp else None)
                    if r["bot_check"] and wait_human:
                        print(f"[{site}] bot check - solve it in the window (up to {wait_human}s)...", flush=True)
                        end = time.monotonic() + wait_human
                        while r["bot_check"] and time.monotonic() < end:
                            page.wait_for_timeout(3000); r = look(page, None)
                except Exception as e:
                    r = {"status": None, "final_url": url, "title": "", "chars": 0, "mentions": 0, "bot_check": False,
                         "items": 0, "examples": [], "error": f"{type(e).__name__}: {str(e)[:80]}"}
                r["url_tried"] = url
                try:
                    page.screenshot(path=str(out / f"{site}_{i + 1}.png"))
                except Exception:
                    pass
                r["verdict"] = verdict(r) if "error" not in r else "could not open: " + r["error"]
                if best is None or (r["items"], r["mentions"]) > (best["items"], best["mentions"]):
                    best = r
                if r["items"]:
                    break
            report[site] = best
            print(f'{site:11} | HTTP {best["status"]} | sorvella x{best["mentions"]} | items {best["items"]} | {best["verdict"]}', flush=True)
        ctx.close()
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


def main():
    out = Path.home() / "sorvella-probe"
    os.environ.setdefault("BROWSER_CHANNEL", "chrome")
    import sys
    sites = {k: v for k, v in SITES.items() if not sys.argv[1:] or k in sys.argv[1:]}
    rep = probe(sites, out)
    print("\n=== COPY FROM HERE ===")
    for site, r in rep.items():
        print(f'{site} | HTTP {r["status"]} | title "{r["title"]}" | sorvella x{r["mentions"]} | items {r["items"]} | {r["verdict"]}'
              + f' | {r["final_url"]}')
        for ex in r["examples"]:
            print(f'    - {ex}')
        if not r["items"]:
            print(f'    page text: {r["snippet"]}')
    print("=== TO HERE ===")
    print(f"Screenshots: {out}")


if __name__ == "__main__":
    main()
