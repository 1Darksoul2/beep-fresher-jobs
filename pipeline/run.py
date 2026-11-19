"""Daily pipeline: collect -> dedupe -> tag -> publish JSON for the static site.

Usage:
    python -m pipeline.run            # full run (needs GEMINI_API_KEY)
    python -m pipeline.run --no-llm   # collect + dedupe only (writes untagged posts)
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config as C
from .dedupe import dedupe
from .sources import collect_all

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE_DATA = ROOT / "docs" / "data"
CACHE = DATA / "tags_cache.json"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_dotenv():
    """Minimal .env loader (KEY=value lines) for local runs; CI uses repo secrets."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    raw, collect_stats = collect_all()
    save_json(DATA / "raw_posts.json", raw)
    posts, dedupe_stats = dedupe(raw)

    cost = None
    cache = load_json(CACHE, {})
    if not args.no_llm:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise SystemExit("GEMINI_API_KEY not set (use --no-llm to skip tagging)")
        from .tagger import Tagger
        tagger = Tagger()
        cache = tagger.tag(posts, cache)
        save_json(CACHE, cache)
        cost = tagger.cost_report()
        print(f"[tag] {cost}")

    published = []
    for p in posts:
        tags = cache.get(p["uid"])
        if tags and not tags["is_fresher"]:
            continue  # LLM says this needs 2+ yrs experience -> not for freshers
        published.append({
            "id": p["uid"], "title": p["title"], "company": p["company"], "type": p["type"],
            "source": p["source"], "url": p["url"], "posted_at": p["posted_at"],
            "location_raw": p["location_raw"],
            "role": tags["role"] if tags else None,
            "city": tags["city"] if tags else None,
        })
    published.sort(key=lambda x: x["posted_at"] or "", reverse=True)
    by_source = {}
    for j in published:
        by_source[j["source"]] = by_source.get(j["source"], 0) + 1
    companies = len({j["company"].lower() for j in published})

    run = {
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.time() - t0, 1),
        "collected": collect_stats,
        "dedupe": dedupe_stats,
        "tagging": cost,
        "published": len(published),
        "published_by_source": by_source,
        "companies": companies,
        "dropped_not_fresher": len(posts) - len(published),
    }
    save_json(SITE_DATA / "jobs.json", {"updated_at": run["finished_at"], "count": len(published),
                                         "roles": C.ROLES, "cities": C.CITIES,
                                         "by_source": by_source, "jobs": published})
    history = load_json(DATA / "runs.json", [])
    history.append(run)
    save_json(DATA / "runs.json", history[-90:])
    save_json(SITE_DATA / "last_run.json", run)
    print(f"[done] published {len(published)} posts in {run['seconds']}s")


if __name__ == "__main__":
    main()
