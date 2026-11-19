"""Score the hand-checked sample: a blank correct_* cell means the LLM was right."""
import csv
from pathlib import Path

rows = list(csv.DictReader((Path(__file__).parent / "sample_50.csv").open(encoding="utf-8-sig")))
n = len(rows)


def acc(llm_col, fix_col):
    wrong = [r for r in rows if r[fix_col].strip() and r[fix_col].strip().lower() != str(r[llm_col]).lower()]
    return (n - len(wrong)) / n, wrong


print(f"Hand-checked posts: {n}\n")
both_ok = 0
for name, llm, fix in [("Role", "llm_role", "correct_role"), ("City", "llm_city", "correct_city"),
                       ("Fresher", "llm_is_fresher", "correct_fresher")]:
    a, wrong = acc(llm, fix)
    print(f"{name:8s} accuracy: {a:6.1%}  ({n - len(wrong)}/{n})")
    for r in wrong:
        print(f"    x {r['title'][:50]!r}: LLM={r[llm]!r} -> {r[fix]!r}")
for r in rows:
    if not r["correct_role"].strip() and not r["correct_city"].strip():
        both_ok += 1
print(f"\nRole AND city both right: {both_ok / n:.1%} ({both_ok}/{n})")
