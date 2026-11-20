"""Collect proof for the three findings.

1. robots.txt of every site considered  -> submission/evidence/robots_<site>.txt + robots_summary.csv
2. per-board counts (total / India / entry-level) for every company board -> submission/evidence/board_counts.csv
3. finder validation: boards dropped as 'wrong company' -> read from data/boards.json
Run: python -m eval.collect_evidence   (from the project root)
"""
import csv
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import config as C                      # noqa: E402
from pipeline.sources import FETCHERS, HOST_DELAY, INDIA, looks_entry_level, load_boards  # noqa: E402

EV = ROOT / "submission" / "evidence"
EV.mkdir(parents=True, exist_ok=True)

SITES = {
    "unstop": "https://unstop.com/robots.txt",
    "naukri": "https://www.naukri.com/robots.txt",
    "indeed_in": "https://in.indeed.com/robots.txt",
    "glassdoor_in": "https://www.glassdoor.co.in/robots.txt",
    "linkedin": "https://www.linkedin.com/robots.txt",
    "internshala": "https://internshala.com/robots.txt",
    "smartrecruiters_api": "https://api.smartrecruiters.com/robots.txt",
    "greenhouse_api": "https://boards-api.greenhouse.io/robots.txt",
    "lever_api": "https://api.lever.co/robots.txt",
}
# what to look for per site: the rule that matters for collecting job posts
KEY = {
    "unstop": r"^(allow|disallow): /(api/public|api/\*|job|internship)",
    "naukri": r"^(user-agent: \*|disallow: /\s*$)",
    "indeed_in": r"^(user-agent: \*|disallow: /(jobs|viewjob|rc/|pagead|m/))",
    "glassdoor_in": r"^(user-agent: \*|disallow: /(jobview|job-listing|Job/))",
    "linkedin": r"^(user-agent: \*|disallow: /\s*$|disallow: /jobs)",
    "internshala": r"^(user-agent: \*|disallow: /(internship|job)/(details|search)|disallow: /api/)",
    "smartrecruiters_api": r"^(user-agent|allow|disallow)",
    "greenhouse_api": r"^(user-agent|allow|disallow)",
    "lever_api": r"^(user-agent|allow|disallow|crawl-delay)",
}


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), str(e)


def robots():
    rows = []
    for site, url in SITES.items():
        status, text = fetch_text(url)
        (EV / f"robots_{site}.txt").write_text(f"# fetched {date.today()} from {url} (HTTP {status})\n{text}", encoding="utf-8")
        hits = [l.strip() for l in text.splitlines() if re.search(KEY[site], l.strip(), re.I)][:6]
        rows.append([site, url, status, str(date.today()), " | ".join(hits)])
        print(f"robots {site}: HTTP {status}, {len(hits)} key lines")
    with (EV / "robots_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["site", "robots_url", "http_status", "date_checked", "key_rules_quoted"])
        w.writerows(rows)


def boards():
    detail = json.loads((ROOT / "data/boards.json").read_text(encoding="utf-8"))["detail"]
    name_of = {(p, v["slug"]): n for p, d in detail.items() for n, v in d.items()}
    out = []
    for platform, slugs in load_boards().items():
        for s in slugs:
            posts = FETCHERS[platform](s)
            india = [p for p in posts if INDIA.search(p["location_raw"])]
            entry = [p for p in india if looks_entry_level(p["title"], p["description"])]
            out.append([platform, s, name_of.get((platform, s), s), len(posts), len(india), len(entry),
                        f"{len(entry) / len(india):.0%}" if india else ""])
            print(f"board {platform}/{s}: total={len(posts)} india={len(india)} entry={len(entry)}")
            time.sleep(HOST_DELAY[platform])
    out.sort(key=lambda r: -r[4])
    with (EV / "board_counts.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["platform", "board_slug", "company", "total_jobs", "india_jobs", "india_entry_level_jobs", "entry_share_of_india"])
        w.writerows(out)
    ti, te = sum(r[4] for r in out), sum(r[5] for r in out)
    print(f"TOTAL india={ti} entry={te} share={te / ti:.1%} boards={len(out)}")


if __name__ == "__main__":
    robots()
    boards()
