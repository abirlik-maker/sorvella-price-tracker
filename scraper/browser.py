"""Browser-based scraper (Playwright). Run: python -m scraper.browser"""
import os
import time
from pathlib import Path
from urllib.parse import quote_plus
from .channels import Channel, Blocked, Unreadable

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Runs inside the page (extract.js). Verified on live allegro.pl and ceneo.pl result pages.
EXTRACT_JS = (Path(__file__).parent / "extract.js").read_text(encoding="utf-8")

BOT_WORDS = ("captcha", "access denied", "just a moment", "attention required", "are you a robot")


class BrowserChannel(Channel):
    def __init__(self, id, name, url):
        self.id, self.name, self.url = id, name, url
        self._pw = self._browser = self._ctx = self._page = None

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

    def search(self, product):
        """Retry once with a fresh browser if the page crashed, timed out or came back empty."""
        for attempt in (1, 2):
            try:
                return self._search(product)
            except Blocked:
                raise
            except Exception as e:           # includes Unreadable, timeouts, "Page crashed"
                if attempt == 2:
                    raise
                print(f"[{self.id}] {type(e).__name__}: retrying once with a fresh browser", flush=True)
                self.close()
                time.sleep(3)

    def _search(self, product):
        if not self._page:
            self._start()
        page = self._page
        resp = page.goto(self.url.format(q=quote_plus(self.query(product))),
                         wait_until="domcontentloaded", timeout=30000)
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

def browser_channels():
    return [
        BrowserChannel("allegro", "Allegro", "https://allegro.pl/listing?string={q}"),
        BrowserChannel("ceneo", "Ceneo", "https://www.ceneo.pl/;szukaj-{q}"),
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
