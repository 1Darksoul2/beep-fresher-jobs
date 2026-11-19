"""Draw a reproducible random sample of 50 tagged posts for hand-checking.

Writes eval/sample_50.csv. Fill in the empty columns by hand:
  correct_role, correct_city, correct_fresher   (leave blank if the LLM was right,
  or type the right value if it was wrong)
Then run: python eval/score.py
"""
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N, SEED = 50, 20261118

raw = {p["uid"]: p for p in json.loads((ROOT / "data/raw_posts.json").read_text(encoding="utf-8"))}
tags = json.loads((ROOT / "data/tags_cache.json").read_text(encoding="utf-8"))
ids = sorted(u for u in tags if u in raw)
random.Random(SEED).shuffle(ids)

out = ROOT / "eval/sample_50.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["uid", "url", "title", "company", "location_raw", "description_start",
                "llm_role", "llm_city", "llm_is_fresher",
                "correct_role", "correct_city", "correct_fresher", "notes"])
    for u in ids[:N]:
        p, t = raw[u], tags[u]
        w.writerow([u, p["url"], p["title"], p["company"], p["location_raw"], p["description"][:300],
                    t["role"], t["city"], t["is_fresher"], "", "", "", ""])
print(f"wrote {out} ({min(N, len(ids))} rows)")
