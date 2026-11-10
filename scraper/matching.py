import re
from .util import core_name, parse_ml

# words that say nothing about WHICH scent/product it is
EXTRA_STOP = {"and", "i", "oraz", "perfume", "parfum", "perfumes", "fragrance", "women", "men",
              "woman", "man", "for", "damskie", "meskie", "kobiet", "mezczyzn", "edp", "wood",
              "w", "z", "sprayu", "szt", "x"}
HOME = re.compile(r"dyfuzor|diffuser|domow|home|room|patyczk|sticks", re.I)
SET = re.compile(r"\b(zestaw|set|discovery|sample|samples|probki|próbki)\b", re.I)


def kind(title):
    if HOME.search(title):
        return "home"
    if SET.search(title):
        return "set"
    return "perfume"


def tokens(title):
    return {w for w in core_name(title).split()
            if w not in EXTRA_STOP and not re.search(r"\d", w)}


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
    if not a or not a <= b:
        return None            # every word of our product name must appear
    extra = len(b - a)
    if extra > 3:
        return None
    flag = extra > 1 or bool(ours["size_ml"] and not size)
    return {"score": 100 - 6 * extra, "flag": flag}
