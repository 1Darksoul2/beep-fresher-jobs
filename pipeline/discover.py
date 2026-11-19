"""Find which hiring platform each company's careers page uses.

Most startups embed an ATS (Greenhouse / Lever / Ashby / Workable) on their careers page.
Those platforms expose an official public job-board API keyed by a "board slug".
This script guesses slugs for each company in data/companies.txt, probes every platform,
and writes the boards that answer to data/boards.json, which the daily run then uses.

Run occasionally (not daily):  python -m pipeline.discover
"""
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config as C

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "data" / "companies.txt"
OUT = ROOT / "data" / "boards.json"

# per-platform: url template, how to count jobs, polite delay between requests (seconds)
PLATFORMS = {
    "greenhouse": ("https://boards-api.greenhouse.io/v1/boards/{s}/jobs", lambda d: len(d.get("jobs", [])), 0.3),
    "lever": ("https://api.lever.co/v0/postings/{s}?mode=json", lambda d: len(d) if isinstance(d, list) else 0, 1.0),
    "ashby": ("https://api.ashbyhq.com/posting-api/job-board/{s}", lambda d: len(d.get("jobs", [])), 0.3),
    "workable": ("https://apply.workable.com/api/v1/widget/accounts/{s}", lambda d: len(d.get("jobs", [])), 0.5),
}


def slugs(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    words = base.split()
    cands = ["".join(words), "-".join(words), words[0]]
    cands += ["".join(words) + "india", "".join(words) + "hq"]
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def probe_platform(platform: str, companies: list[str]) -> dict[str, dict]:
    """Sequential per platform (respects that host's rate), platforms run in parallel."""
    tmpl, count, delay = PLATFORMS[platform]
    found = {}
    for name in companies:
        for s in slugs(name):
            d = fetch(tmpl.format(s=s))
            time.sleep(delay)
            if d is None:
                continue
            n = count(d)
            if n > 0:
                found[name] = {"slug": s, "jobs": n}
                print(f"  + {platform:10s} {name} -> {s} ({n} jobs)")
                break
    return found


def validate(results: dict[str, dict[str, dict]]) -> dict[str, dict[str, dict]]:
    """Slug guesses collide with unrelated companies (a US nurse-staffing 'Porter' vs the Indian
    logistics 'Porter'). A real Indian-hiring board must have at least one India-located job."""
    from .sources import FETCHERS, INDIA
    good = {}
    for platform, found in results.items():
        good[platform] = {}
        for name, v in found.items():
            posts = FETCHERS[platform](v["slug"])
            n = sum(1 for p in posts if INDIA.search(p["location_raw"]))
            time.sleep(PLATFORMS[platform][2])
            if n:
                good[platform][name] = {**v, "india_jobs": n}
            else:
                print(f"  - dropped {platform} {name} -> {v['slug']} (0 India jobs, probably a different company)")
    return good


def main():
    companies = [l.strip() for l in COMPANIES.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
    print(f"[discover] probing {len(companies)} companies on {len(PLATFORMS)} platforms")
    with ThreadPoolExecutor(len(PLATFORMS)) as ex:
        results = dict(zip(PLATFORMS, ex.map(lambda p: probe_platform(p, companies), PLATFORMS)))
    results = validate(results)
    boards = {p: sorted({v["slug"] for v in r.values()}) for p, r in results.items()}
    OUT.write_text(json.dumps({"boards": boards, "detail": results}, indent=1), encoding="utf-8")
    hit = {n for r in results.values() for n in r}
    print(f"[discover] {len(hit)}/{len(companies)} companies found on a public ATS -> {OUT}")
    for p, b in boards.items():
        print(f"  {p}: {len(b)} boards")


if __name__ == "__main__":
    import sys
    if "--revalidate" in sys.argv:   # re-check boards already in boards.json without re-probing
        old = json.loads(OUT.read_text(encoding="utf-8"))["detail"]
        res = validate(old)
        boards = {p: sorted({v["slug"] for v in r.values()}) for p, r in res.items()}
        OUT.write_text(json.dumps({"boards": boards, "detail": res}, indent=1), encoding="utf-8")
        print({p: len(b) for p, b in boards.items()})
    else:
        main()
