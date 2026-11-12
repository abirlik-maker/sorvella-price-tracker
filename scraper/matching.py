import re
from rapidfuzz import fuzz
from .util import core_name, parse_ml

# words that say nothing about WHICH scent/product it is
EXTRA_STOP = {"and", "i", "oraz", "perfume", "parfum", "perfumes", "fragrance", "women", "men",
              "woman", "man", "for", "damskie", "meskie", "kobiet", "mezczyzn", "edp", "wood",
              "w", "z", "sprayu", "szt", "x", "eau", "de", "toilette", "s", "sticks"}
HOME = re.compile(r"dyfuzor|diffuser|domow|home|room|patyczk|sticks", re.I)
SET = re.compile(r"\b(zestaw|set|discovery|sample|samples|probki|próbki)\b", re.I)
CODE = re.compile(r"^[a-z]{1,4}\d{1,3}$")      # product codes such as S530, V622, MLC2


def kind(title):
    if HOME.search(title):
        return "home"
    if SET.search(title):
        return "set"
    return "perfume"


def tokens(title):
    # "S-530", "S 530" and "S530" are the same code (but not the "s" in "women's")
    t = re.sub(r"(?<![\w'’])([sv])[\s\-–—]?(\d{2,3})\b", r"\1\2", title.lower())
    return {w for w in core_name(t).split() if w not in EXTRA_STOP and (CODE.match(w) or not re.search(r"\d", w))}


def covers(a, b):
    """Every word of `a` is in `b`, allowing one-letter spelling differences (Vanilia/Vanilla, Cardamon/Cardamom)."""
    return all(t in b or (len(t) >= 5 and any(fuzz.ratio(t, u) >= 84 for u in b)) for t in a)


def match(ours, cand):
    """Is this competitor listing the same product as ours? None, or {score, flag}."""
    if "sorvella" not in cand["title"].lower():
        return None
    if kind(ours["title"]) != kind(cand["title"]):
        return None
    size = parse_ml(cand["title"])
    if ours["size_ml"] and size and size != ours["size_ml"]:
        return None
    a, b = tokens(ours["title"]), tokens(cand["title"])
    codes = {t for t in a if CODE.match(t)}
    if codes:                      # coded products: the code identifies the product
        if not covers(codes, b):
            return None
        return {"score": 100, "flag": bool(ours["size_ml"] and not size)}
    if not a or not covers(a, b):
        return None                # every word of our product name must appear
    extra = len([u for u in b if u not in a and not any(fuzz.ratio(u, t) >= 84 and len(t) >= 5 for t in a)])
    if extra > 3:
        return None
    flag = extra > 1 or bool(ours["size_ml"] and not size)
    return {"score": 100 - 6 * extra, "flag": flag}
