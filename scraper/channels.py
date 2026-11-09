import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
from .util import parse_price, core_name

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class Blocked(Exception):
    pass


class Unreadable(Exception):
    pass


class Disabled(Exception):
    pass


class Channel:
    id = name = ""

    def search(self, product):
        raise NotImplementedError

    @staticmethod
    def query(product):
        size = f' {product["size_ml"]}ml' if product["size_ml"] else ""
        return f'sorvella {core_name(product["title"])}{size}'


class Allegro(Channel):
    id, name = "allegro", "Allegro"
    _token = None

    def _auth(self):
        cid, sec = os.getenv("ALLEGRO_CLIENT_ID"), os.getenv("ALLEGRO_CLIENT_SECRET")
        if not (cid and sec):
            raise Disabled("ALLEGRO_CLIENT_ID / ALLEGRO_CLIENT_SECRET not set")
        r = requests.post("https://allegro.pl/auth/oauth/token",
                          params={"grant_type": "client_credentials"},
                          auth=(cid, sec), timeout=30)
        r.raise_for_status()
        self._token = r.json()["access_token"]

    def search(self, product):
        if not self._token:
            self._auth()
        r = requests.get("https://api.allegro.pl/offers/listing",
                         params={"phrase": self.query(product), "limit": 30},
                         headers={"Authorization": f"Bearer {self._token}",
                                  "Accept": "application/vnd.allegro.public.v1+json"},
                         timeout=30)
        if r.status_code in (403, 429):
            raise Blocked(f"HTTP {r.status_code}")
        r.raise_for_status()
        items = r.json().get("items", {})
        out = []
        for o in items.get("promoted", []) + items.get("regular", []):
            try:
                out.append({"title": o["name"],
                            "price": float(o["sellingMode"]["price"]["amount"]),
                            "url": f'https://allegro.pl/oferta/{o["id"]}'})
            except (KeyError, ValueError):
                continue
        return out


class HtmlChannel(Channel):
    """Seçicisiz çalışır: sayfadaki 'sorvella' geçen bağlantıları ve yakınındaki fiyatı arar.
    Sayfa JavaScript ile yükleniyorsa Unreadable fırlatır (Playwright gerekir)."""

    def __init__(self, id, name, url):
        self.id, self.name, self.url = id, name, url

    def search(self, product):
        r = requests.get(self.url.format(q=quote_plus(self.query(product))),
                         headers={"User-Agent": BROWSER_UA, "Accept-Language": "pl-PL,pl;q=0.9"},
                         timeout=30)
        if r.status_code in (403, 429, 503):
            raise Blocked(f"HTTP {r.status_code}")
        r.raise_for_status()
        html = r.text
        if "captcha" in html[:20000].lower():
            raise Blocked("captcha")
        if "sorvella" not in html.lower():
            raise Unreadable("results page unreadable (probably rendered with JavaScript)")
        soup = BeautifulSoup(html, "html.parser")
        out, seen = [], set()
        for a in soup.find_all("a", href=True):
            title = a.get("title") or a.get_text(" ", strip=True)
            if "sorvella" not in (title + a["href"]).lower() or len(title) < 8:
                continue
            url = urljoin(r.url, a["href"])
            if url in seen:
                continue
            node, price = a, None
            for _ in range(5):
                node = node.parent
                if node is None:
                    break
                price = parse_price(node.get_text(" ", strip=True))
                if price:
                    break
            if price:
                seen.add(url)
                out.append({"title": title, "price": price, "url": url})
        return out


def all_channels():
    return [
        Allegro(),
        HtmlChannel("ceneo", "Ceneo", "https://www.ceneo.pl/;szukaj-{q}"),
        HtmlChannel("notino", "Notino", "https://www.notino.pl/search.html?f={q}"),
        HtmlChannel("douglas", "Douglas", "https://www.douglas.pl/search?q={q}"),
        HtmlChannel("sephora", "Sephora", "https://www.sephora.pl/search?q={q}"),
        HtmlChannel("rossmann", "Rossmann", "https://www.rossmann.pl/szukaj?Query={q}"),
        HtmlChannel("hebe", "Hebe", "https://www.hebe.pl/search?q={q}"),
        HtmlChannel("superpharm", "Super-Pharm", "https://www.superpharm.pl/search?q={q}"),
    ]
