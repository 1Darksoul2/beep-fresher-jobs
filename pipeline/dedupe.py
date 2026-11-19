"""Duplicate removal.

Layer 1: exact uid / URL.
Layer 2: normalized (company, title, location) key.
Layer 3: fuzzy title match (>= 0.92 similarity) within the same company + location,
         catches "SDE Intern - 2026" vs "SDE Intern (2026 batch)" reposts.
"""
import re
from difflib import SequenceMatcher

_NOISE = re.compile(
    r"\b(pvt|private|ltd|limited|llp|inc|technologies|technology|solutions|india|"
    r"services|software|labs|the)\b|[^a-z0-9 ]"
)


def norm(s: str) -> str:
    s = (s or "").lower()
    s = _NOISE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def dedupe(posts: list[dict]) -> tuple[list[dict], dict]:
    seen_uid, seen_url, seen_key = set(), set(), set()
    by_company: dict[str, list[str]] = {}
    kept, reasons = [], {"uid": 0, "url": 0, "key": 0, "fuzzy": 0}

    for p in posts:
        if p["uid"] in seen_uid:
            reasons["uid"] += 1
            continue
        url = (p.get("url") or "").split("?")[0].rstrip("/").lower()
        if url and url in seen_url:
            reasons["url"] += 1
            continue
        comp, title, loc = norm(p["company"]), norm(p["title"]), norm(p["location_raw"])
        key = f"{comp}|{title}|{loc}"
        if key in seen_key:
            reasons["key"] += 1
            continue
        bucket = by_company.setdefault(f"{comp}|{loc}", [])
        if any(SequenceMatcher(None, title, t).ratio() >= 0.92 for t in bucket):
            reasons["fuzzy"] += 1
            continue
        seen_uid.add(p["uid"])
        if url:
            seen_url.add(url)
        seen_key.add(key)
        bucket.append(title)
        kept.append(p)

    stats = {"input": len(posts), "kept": len(kept), "removed": len(posts) - len(kept), "by_reason": reasons}
    print(f"[dedupe] {stats}")
    return kept, stats
