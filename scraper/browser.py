"""Browser-based scraper (Playwright). Run: python -m scraper.browser"""
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
        self._pw = self._browser = self._page = None

    def _start(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = self._browser.new_context(locale="pl-PL", timezone_id="Europe/Warsaw",
                                        viewport={"width": 1366, "height": 900}, user_agent=UA)
        ctx.route("**/*", lambda r: r.abort()
                  if r.request.resource_type in ("image", "media", "font") else r.continue_())
        self._page = ctx.new_page()

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._page = None

    def search(self, product):
        if not self._page:
            self._start()
        page = self._page
        resp = page.goto(self.url.format(q=quote_plus(self.query(product))),
                         wait_until="domcontentloaded", timeout=30000)
        if resp is not None and resp.status in (403, 429, 503):
            raise Blocked(f"HTTP {resp.status}")
        page.wait_for_timeout(1200)
        title = (page.title() or "").lower()
        body = page.inner_text("body")
        if any(w in title for w in BOT_WORDS) or any(w in body[:1500].lower() for w in BOT_WORDS):
            raise Blocked("bot check: " + title[:60])
        if len(body) < 400:
            raise Unreadable("page rendered almost empty")
        return page.evaluate(EXTRACT_JS)


def browser_channels():
    return [
        BrowserChannel("allegro", "Allegro", "https://allegro.pl/listing?string={q}"),
        BrowserChannel("ceneo", "Ceneo", "https://www.ceneo.pl/;szukaj-{q}"),
    ]


def main():
    from . import run
    run.all_channels = browser_channels
    run.CHANNEL_BUDGET = 600   # browser pages are slower than plain requests
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
