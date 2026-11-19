"""Score the checked sample.

correct_*   : set only where the LLM was clearly wrong.
ambiguous_* : set where a careful human could defend either answer.
Strict score counts ambiguous rows as wrong; lenient score counts them as right.
"""
import csv
from pathlib import Path

rows = list(csv.DictReader((Path(__file__).parent / "sample_50.csv").open(encoding="utf-8-sig")))
n = len(rows)
print(f"Checked posts: {n}\n")
print(f"{'Field':8s} {'strict':>8s} {'lenient':>8s}   clear errors / ambiguous")
for name, key in [("Role", "role"), ("City", "city"), ("Fresher", "fresher")]:
    clear = [r for r in rows if r[f"correct_{key}"].strip()]
    amb = [r for r in rows if r[f"ambiguous_{key}"].strip() and not r[f"correct_{key}"].strip()]
    print(f"{name:8s} {(n - len(clear) - len(amb)) / n:8.0%} {(n - len(clear)) / n:8.0%}   {len(clear)} / {len(amb)}")
    for r in clear:
        print(f"    ERROR     {r['title'][:42]!r}: LLM={r['llm_' + ('is_fresher' if key == 'fresher' else key)]!r} -> {r['correct_' + key]!r}")
    for r in amb:
        print(f"    AMBIGUOUS {r['title'][:42]!r}: LLM={r['llm_' + ('is_fresher' if key == 'fresher' else key)]!r} vs {r['ambiguous_' + key]!r}")
both_strict = sum(1 for r in rows if not any(r[f"{c}_{k}"].strip() for c in ("correct", "ambiguous") for k in ("role", "city")))
both_len = sum(1 for r in rows if not any(r[f"correct_{k}"].strip() for k in ("role", "city")))
print(f"\nRole AND city both right: strict {both_strict / n:.0%}, lenient {both_len / n:.0%}")
