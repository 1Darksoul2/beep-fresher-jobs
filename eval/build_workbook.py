"""Build submission/beep_submission.xlsx: data, accuracy check, tools, prompts, run stats."""
import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "submission" / "beep_submission.xlsx"
OUT.parent.mkdir(exist_ok=True)

jobs = json.loads((ROOT / "docs/data/jobs.json").read_text(encoding="utf-8"))
runs = json.loads((ROOT / "data/runs.json").read_text(encoding="utf-8"))
sample = list(csv.DictReader((ROOT / "eval/sample_50.csv").open(encoding="utf-8-sig")))

# cost over every run that called the LLM (a single run's per-1k figure is noisy when it tags 1 post)
tagged = [r["tagging"] for r in runs if r.get("tagging")]
posts = sum(t["posts"] for t in tagged)
cost = sum(t["cost_usd"] for t in tagged)
tin = sum(t["input_tokens"] for t in tagged)
tout = sum(t["output_tokens"] for t in tagged)

n = len(sample)
def score(key):
    clear = sum(1 for r in sample if r[f"correct_{key}"].strip())
    amb = sum(1 for r in sample if r[f"ambiguous_{key}"].strip() and not r[f"correct_{key}"].strip())
    return (n - clear - amb) / n, (n - clear) / n, clear, amb
role, city, fresh = score("role"), score("city"), score("fresher")

wb = Workbook()
HEAD = Font(bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F4E79")

def sheet(title, header, rows, widths=None, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(header)
    for c in ws[1]:
        c.font, c.fill = HEAD, FILL
    for r in rows:
        ws.append(r)
    ws.freeze_panes = "A2"
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    return ws

by_src = jobs["by_source"]
summary = [
    ["Live site", "https://1darksoul2.github.io/beep-fresher-jobs/"],
    ["Repo", "https://github.com/1Darksoul2/beep-fresher-jobs"],
    ["Posts published", jobs["count"]],
    ["Companies", len({j["company"].lower() for j in jobs["jobs"]})],
    ["Posts by source", ", ".join(f"{k} {v}" for k, v in sorted(by_src.items(), key=lambda x: -x[1]))],
    ["Tagging model", "gemini-3.5-flash-lite (thinking_level=low), 20 posts per call, JSON-schema output"],
    ["", ""],
    ["ACCURACY (50 random posts, fixed seed 20261118)", "strict = ambiguous counted wrong; lenient = ambiguous counted right"],
    ["Role accuracy", f"strict {role[0]:.0%} / lenient {role[1]:.0%}  ({role[2]} clear errors, {role[3]} ambiguous)"],
    ["City accuracy", f"strict {city[0]:.0%} / lenient {city[1]:.0%}  ({city[2]} clear errors, {city[3]} ambiguous)"],
    ["Fresher-flag accuracy", f"strict {fresh[0]:.0%} / lenient {fresh[1]:.0%}  ({fresh[2]} clear errors, {fresh[3]} ambiguous)"],
    ["", ""],
    ["COST (paid-tier prices, all tagging runs combined)", ""],
    ["Posts tagged", posts],
    ["Tokens in / out", f"{tin:,} / {tout:,}  (thinking tokens: 0)"],
    ["Total cost (USD)", round(cost, 4)],
    ["Cost per 1,000 posts (USD)", round(cost / posts * 1000, 3)],
    ["Price used", "$0.30 per 1M input tokens, $2.50 per 1M output tokens (gemini-3.5-flash-lite). Free tier: $0."],
    ["Daily cost at steady state", "Only NEW posts are tagged (cache by post id): typically well under $0.02 per day."],
]
ws = sheet("Summary", ["Item", "Value"], summary, [48, 110], first=True)
for r in ws.iter_rows(min_row=2):
    r[1].alignment = Alignment(wrap_text=True, vertical="top")
    if str(r[0].value).isupper() or str(r[0].value).startswith(("ACCURACY", "COST")):
        r[0].font = Font(bold=True)

sheet("Jobs data", ["id", "title", "company", "type", "role", "city", "location_raw", "source", "posted_at", "url"],
      [[j["id"], j["title"], j["company"], j["type"], j["role"], j["city"], j["location_raw"], j["source"],
        j["posted_at"], j["url"]] for j in jobs["jobs"]], [22, 48, 32, 12, 30, 16, 28, 12, 26, 70])

cols = ["uid", "url", "title", "company", "location_raw", "llm_role", "llm_city", "llm_is_fresher",
        "correct_role", "correct_city", "correct_fresher", "ambiguous_role", "ambiguous_city", "ambiguous_fresher", "notes"]
sheet("Accuracy check (50)", cols, [[r[c] for c in cols] for r in sample],
      [20, 50, 40, 28, 22, 28, 14, 12, 18, 14, 14, 22, 16, 14, 70])

sheet("AI tools used", ["Tool", "Used for"], [
    ["Claude Code (Claude, Anthropic)", "Pair-programmed the pipeline: source research, collectors, de-duplication, static site, GitHub Actions workflow, eval scripts. I chose the sources, the respect-the-terms policy and the taxonomy; the code was written together."],
    ["Claude (same session)", "First-pass review of the 50-post sample against the full post text: flagged clear errors and ambiguous cases. These judgments are AI-assisted, not a fully independent human check."],
    ["Google Gemini 3.5 Flash-Lite", "Runtime LLM: tags every post with role, city and is_fresher."],
    ["Google AI Studio", "API key and pricing reference."],
    ["GitHub Actions + Pages", "Daily 06:00 IST refresh and free static hosting."],
], [36, 140])

import sys
sys.path.insert(0, str(ROOT))
from pipeline.tagger import SYSTEM_PROMPT, SCHEMA
sheet("Prompts", ["Name", "Text"], [
    ["System prompt (tagger)", SYSTEM_PROMPT],
    ["User prompt template", 'Label these posts:\n\n<post id="0">\ntitle: ...\ncompany: ...\ntype: Job|Internship\nlocation: ...\ndescription: first 700 chars\n</post>\n... (20 posts per call)'],
    ["Output JSON schema", json.dumps(SCHEMA, indent=1)],
    ["Settings", "model=gemini-3.5-flash-lite, response_mime_type=application/json, response_json_schema=<schema above>, thinking_level=low, max_output_tokens=8000"],
], [26, 140])

sheet("Run stats", ["finished_at", "seconds", "collected", "kept after dedupe", "removed by dedupe", "dedupe reasons", "published", "LLM posts tagged", "LLM cost USD"],
      [[r["finished_at"], r["seconds"], sum(v["count"] for v in r["collected"].values()), r["dedupe"]["kept"],
        r["dedupe"]["removed"], json.dumps(r["dedupe"]["by_reason"]), r["published"],
        (r.get("tagging") or {}).get("posts"), (r.get("tagging") or {}).get("cost_usd")] for r in runs],
      [26, 10, 12, 16, 16, 44, 10, 16, 12])

wb.save(OUT)
print("saved", OUT, "| cost per 1k:", round(cost / posts * 1000, 3), "| posts tagged:", posts, "| role/city/fresh strict:", f"{role[0]:.0%}/{city[0]:.0%}/{fresh[0]:.0%}")
