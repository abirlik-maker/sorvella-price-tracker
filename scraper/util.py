import re

SIZE_RE = re.compile(r"(\d{1,4})\s?ml\b", re.I)
PRICE_RE = re.compile(r"(\d{1,3}(?:[\s\u00a0.]\d{3})*(?:[.,]\d{1,2})|\d+(?:[.,]\d{1,2}))\s?(?:zł|pln)", re.I)

STOP = {
    "perfumy", "perfum", "zapach", "domowy", "do", "domu", "unisex", "damskie", "meskie",
    "męskie", "sorvella", "signature", "mountain", "galaxy", "premium", "standard",
    "woda", "perfumowana", "edp", "ml", "mgiełka", "mgielka", "spray", "dyfuzor",
}


def parse_ml(*texts):
    for t in texts:
        m = SIZE_RE.search(t or "")
        if m:
            return int(m.group(1))
    return None


def parse_price(text):
    m = PRICE_RE.search(text or "")
    if not m:
        return None
    s = m.group(1).replace("\u00a0", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def core_name(title):
    t = re.sub(r"\d+\s?ml", " ", (title or "").lower())
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(w for w in t.split() if w not in STOP and not w.isdigit())
