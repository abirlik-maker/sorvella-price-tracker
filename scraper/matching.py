from rapidfuzz import fuzz
from .util import core_name, parse_ml

ACCEPT, SURE = 80, 92


def match(ours, cand):
    """Rakip ilanı bizim ürünle aynı mı? Değilse None, öyleyse {score, flag}."""
    if "sorvella" not in cand["title"].lower():
        return None
    size = parse_ml(cand["title"])
    if ours["size_ml"] and size and size != ours["size_ml"]:
        return None
    score = fuzz.token_sort_ratio(core_name(ours["title"]), core_name(cand["title"]))
    if score < ACCEPT:
        return None
    flag = score < SURE or (ours["size_ml"] and not size)
    return {"score": round(score), "flag": bool(flag)}
