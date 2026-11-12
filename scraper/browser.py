"""Browser-based scraper (Playwright). Run: python -m scraper.browser"""
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote_plus
from .channels import Channel, Blocked, Unreadable

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Runs inside the page (extract.js). Verified on live allegro.pl and ceneo.pl result pages.
EXTRACT_JS = (Path(__file__).parent / "extract.js").read_text(encoding="utf-8")

BOT_WORDS = ("captcha", "access denied", "just a moment", "attention required", "are you a robot")
TOTAL_RE = re.compile(r"(\d+)\s*(?:products|produkt\w*)|(?:liczba produkt\w*|number of products)\s*:?\s*(\d+)", re.I)
DIAG_JS = r"""() => {
  const out = [], w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode()) && out.length < 2) {
    if (!/sorvella/i.test(n.nodeValue) || !n.parentElement.offsetParent) continue;
    let card = n.parentElement;
    for (let i = 0; i < 8 && card && !/\d/.test((card.innerText || '').replace(/sorvella/ig, '')); i++) card = card.parentElement;
    for (let i = 0; i < 3 && card && card.parentElement && (card.innerText || '').length < 120; i++) card = card.parentElement;
    out.push({text: n.nodeValue.trim().slice(0, 60), card_text: card ? card.innerText.replace(/\s+/g, ' ').slice(0, 200) : null,
              card_html: card ? card.outerHTML.replace(/\s+/g, ' ').slice(0, 800) : null});
  }
  return out;
}"""
PAGINATION_JS = r"""() => {
  const cur = new URL(location.href), keys = /^(page|p|pg|strona|start|offset|pagenumber|currentpage)$/i, out = new Map();
  for (const a of document.querySelectorAll('a[href]')) {
    let u; try { u = new URL(a.href, location.href); } catch (e) { continue; }
    if (u.origin !== cur.origin || u.href === cur.href) continue;
    let val = null;
    for (const [k, v] of u.searchParams) if (keys.test(k) && /^\d+$/.test(v)) val = +v;
    const nav = a.closest('nav, [class*="pagination" i], [class*="pager" i], [aria-label*="pagin" i], [aria-label*="stron" i]');
    const num = /^\d+$/.test((a.textContent || '').trim()) ? +(a.textContent.trim()) : null;
    if (val === null && !(nav && num !== null)) continue;
    if (u.pathname !== cur.pathname && !(nav && num !== null)) continue;
    out.set(u.href, val !== null ? val : num);
  }
  return [...out.entries()].sort((x, y) => x[1] - y[1]).map(x => x[0]);
}"""
NEXT_BUTTONS = ("a[rel='next'], [aria-label*='następn' i], [aria-label*='next' i], button:has-text('Następna'), "
                "a:has-text('Następna'), button:has-text('Next'), a:has-text('Next'), li.next a, .pagination .next a")
MORE_BUTTONS = ("button:has-text('Pokaż więcej'), button:has-text('Załaduj więcej'), button:has-text('Show more'), "
                "button:has-text('Load more'), a:has-text('Pokaż więcej'), a:has-text('Załaduj więcej')")


class BrowserChannel(Channel):
    """One search per product (Allegro, Ceneo)."""

    def __init__(self, id, name, url):
        self.id, self.name, self.url = id, name, url
        self._pw = self._browser = self._ctx = self._page = None
        self._seen = self._with_seller = 0

    def _start(self):
        from playwright.sync_api import sync_playwright
        headless = os.getenv("HEADLESS", "1") != "0"
        channel = os.getenv("BROWSER_CHANNEL") or None   # "chrome" = the real installed Chrome
        profile = os.getenv("PROFILE_DIR")               # keeps cookies between runs
        opts = dict(headless=headless, channel=channel,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    locale="pl-PL", timezone_id="Europe/Warsaw",
                    viewport={"width": 1366, "height": 900})
        if not channel:
            opts["user_agent"] = UA      # never fake the identity of a real Chrome
        self._pw = sync_playwright().start()
        if profile:
            self._ctx = self._pw.chromium.launch_persistent_context(str(Path(profile) / self.id), **opts)
        else:
            self._browser = self._pw.chromium.launch(
                **{k: v for k, v in opts.items() if k in ("headless", "channel", "args", "ignore_default_args")})
            ctx_opts = {k: v for k, v in opts.items() if k in ("locale", "timezone_id", "viewport", "user_agent")}
            self._ctx = self._browser.new_context(**ctx_opts)
        if headless:   # on servers skip images/fonts for speed; on a real desktop load everything
            self._ctx.route("**/*", lambda r: r.abort()
                            if r.request.resource_type in ("image", "media", "font") else r.continue_())
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    def close(self):
        if self._seen:
            print(f"[{self.id}] listings read: {self._seen}, with seller info: {self._with_seller}", flush=True)
            self._seen = self._with_seller = 0
        try:
            if self._ctx:
                self._ctx.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._ctx = self._page = None

    @staticmethod
    def _block_reason(page, status):
        if status in (403, 429, 503):
            return f"HTTP {status}"
        title = (page.title() or "").lower()
        for w in BOT_WORDS:
            if w in title:
                return f"bot check (title): {w!r}"
        body = page.inner_text("body")
        if len(body) < 2500:     # challenge pages are short; real result pages are long
            low = body.lower()
            for w in BOT_WORDS:
                if w in low:
                    return f"bot check (page): {w!r}"
        return None

    def _open(self, url, settle=False):
        """Load a results page. Returns its listings; raises Blocked / Unreadable."""
        page = self._page
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if settle:
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
        page.wait_for_timeout(1200)
        items = page.evaluate(EXTRACT_JS)
        if items:
            return items         # a page with real results is never a bot check
        reason = self._block_reason(page, resp.status if resp is not None else None)
        wait = int(os.getenv("HUMAN_WAIT", "0"))
        if reason and wait:
            print(f"[{self.id}] {reason}. Solve it in the Chrome window, waiting up to {wait}s...", flush=True)
            end = time.monotonic() + wait
            while reason and time.monotonic() < end:
                page.wait_for_timeout(3000)
                items = page.evaluate(EXTRACT_JS)
                if items:
                    return items
                reason = self._block_reason(page, None)
        if reason:
            raise Blocked(reason)
        if len(page.inner_text("body")) < 400:
            raise Unreadable("page rendered almost empty")
        return []

    def _with_retry(self, fn, *args):
        """Retry once with a fresh browser if the page crashed, timed out or came back empty."""
        for attempt in (1, 2):
            try:
                return fn(*args)
            except Blocked:
                raise
            except Exception as e:           # includes Unreadable, timeouts, "Page crashed"
                if attempt == 2:
                    raise
                print(f"[{self.id}] {type(e).__name__}: retrying once with a fresh browser", flush=True)
                self.close()
                time.sleep(3)

    def search(self, product):
        items = self._with_retry(self._search, product)
        self._seen += len(items); self._with_seller += sum(1 for i in items if i.get("seller"))
        return items

    def _search(self, product):
        if not self._page:
            self._start()
        return self._open(self.url.format(q=quote_plus(self.query(product))))


class CatalogChannel(BrowserChannel):
    """Shops with a modest number of Sorvella products (Hebe, Rossmann): read the whole
    'sorvella' result list once, then match our products against it locally."""

    def __init__(self, id, name, url, page_url=None, max_pages=10):
        super().__init__(id, name, url)
        self.page_url, self.max_pages, self._items = page_url, max_pages, None

    def search(self, product):
        if self._items is None:
            self._items = self._with_retry(self._collect)
        return self._items

    def _declared_total(self):
        m = TOTAL_RE.search(self._page.inner_text("body")[:6000])
        return int(m.group(1) or m.group(2)) if m else None

    def _collect(self):
        if not self._page:
            self._start()
        page, found, q = self._page, {}, quote_plus("sorvella")
        pages = 0
        if self.page_url:                                  # numbered pages
            for n in range(1, self.max_pages + 1):
                new = [i for i in self._open(self.page_url.format(page=n, q=q), settle=True) if i["url"] not in found]
                for i in new:
                    found[i["url"]] = i
                if not new:
                    break
                pages += 1
        else:                                              # one result list across several pages
            for i in self._open(self.url.format(q=q), settle=True):
                found[i["url"]] = i
            visited, still, pages = {page.url}, 0, 1
            for _ in range(self.max_pages * 3):
                before = len(found)
                nxt = [h for h in page.evaluate(PAGINATION_JS) if h not in visited]
                if nxt:                                    # 1) numbered page links, any parameter name
                    visited.add(nxt[0]); pages += 1
                    for i in self._open(nxt[0], settle=True):
                        found.setdefault(i["url"], i)
                else:                                      # 2) "next" button, "show more" button, infinite scroll
                    clicked = False
                    for sel in (NEXT_BUTTONS, MORE_BUTTONS):
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible(timeout=300) and btn.is_enabled(timeout=300):
                                btn.click(); clicked = True; pages += 1
                                page.wait_for_timeout(2500)
                                break
                        except Exception:
                            pass
                    if not clicked:
                        page.mouse.wheel(0, 5000)
                        page.wait_for_timeout(1500)
                    for i in page.evaluate(EXTRACT_JS):
                        found.setdefault(i["url"], i)
                still = still + 1 if len(found) == before else 0
                if still >= 2:
                    break
        try:
            out_dir = Path(os.getenv("CATALOG_DUMP_DIR") or Path(__file__).resolve().parent.parent / "docs" / "data")
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"catalog_{self.id}.json").write_text(json.dumps(list(found.values()), ensure_ascii=False, indent=1))
        except Exception:
            pass
        total = self._declared_total()
        print(f"[{self.id}] sellers captured: {sum(1 for i in found.values() if i.get('seller'))} of {len(found)}", flush=True)
        print(f"[{self.id}] catalog read: {len(found)} products" + (f" (page says {total})" if total else "")
              + f", {pages} pages", flush=True)
        if not found and (total or "sorvella" in page.inner_text("body").lower()):
            print(f"[{self.id}] WARNING: the page mentions Sorvella but no product could be read. Send this block:", flush=True)
            print("=== DIAGNOSTIC " + self.id + " ===", flush=True)
            for hit in page.evaluate(DIAG_JS):
                print(hit, flush=True)
            print("=== END DIAGNOSTIC ===", flush=True)
        return list(found.values())


def browser_channels():
    return [
        BrowserChannel("allegro", "Allegro", "https://allegro.pl/listing?string={q}"),
        CatalogChannel("ceneo", "Ceneo", "https://www.ceneo.pl/;szukaj-{q}"),
        CatalogChannel("hebe", "Hebe", "https://www.hebe.pl/search?q={q}&lang=pl_PL"),
        CatalogChannel("rossmann", "Rossmann", "https://www.rossmann.pl/szukaj?Search={q}",
                       page_url="https://www.rossmann.pl/szukaj?Page={page}&Search={q}"),
    ]


def main():
    from . import run
    run.all_channels = browser_channels
    run.CHANNEL_BUDGET = int(os.getenv("CHANNEL_BUDGET", "600"))  # browser pages are slower
    orig = run.scrape_channel

    def scrape_and_close(c, products, ignore_urls):
        try:
            return orig(c, products, ignore_urls)
        finally:
            c.close()

    run.scrape_channel = scrape_and_close
    run.main()


if __name__ == "__main__":
    main()
