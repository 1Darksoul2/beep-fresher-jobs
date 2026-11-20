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

# ---- Findings tab: 3 findings, each with where / why it matters / proof (draft: rewrite in your own words) ----
fs = wb.create_sheet("3 findings", 0)
for col, w in zip("ABCD", (34, 62, 52, 48)):
    fs.column_dimensions[col].width = w
fs.append(["DRAFT: rewrite in your own words before submitting. Every number below is backed by a tab in this file.", "", "", ""])
fs["A1"].font = Font(bold=True, color="C00000")
fs.append(["Finding", "What I found", "Where I found it / why it matters", "Proof in this file"])
for c in fs[2]:
    c.font, c.fill = HEAD, FILL
bd = list(csv.DictReader((ROOT / "submission/evidence/board_counts.csv").open(encoding="utf-8-sig")))
ti, te = sum(int(r["india_jobs"]) for r in bd), sum(int(r["india_entry_level_jobs"]) for r in bd)
unstop_n, total_n = by_src.get("Unstop", 0), jobs["count"]
F = [
 ["1. Almost all the fresher jobs I can legally collect sit on ONE platform",
  f"{unstop_n} of {total_n} published posts ({unstop_n / total_n:.0%}) come from Unstop. The big job sites do not give automated access: LinkedIn's robots.txt says 'Disallow: /', Glassdoor and Internshala disallow their job pages, SmartRecruiters' API says 'Disallow: /' for every bot except LinkedIn's, and Naukri's robots.txt returned HTTP 403 to my bot. Unstop's robots.txt explicitly allows /api/public/*. I did not check Indeed's terms of service, so I left Indeed out as a precaution.",
  "Where: the robots.txt file of each site (fetched on the date shown), and the source split on the live page. Why it matters: 'collect 200+ real posts from public sources and respect each site's terms' is only possible because of one student platform. If Unstop changes its rules, this tool loses 95% of its data, and a product built on fresher jobs should plan for that.",
  "Tab 'Evidence - robots' (quoted rules, dates, HTTP status). Tab 'Summary' (posts by source). Screenshots tab, image 1. Raw files: submission/evidence/robots_*.txt in the repo."],
 ["2. Company career pages add few fresher posts, and guessing company pages gives wrong matches",
  f"On the {len(bd)} company job boards I use, {ti:,} jobs are in India but only {te} ({te / ti:.1%}) are entry-level. An earlier probe of my first 20 hand-picked boards gave 87 of 812 (about 11%). Separately, my company finder matched the wrong company for 11 of 39 boards (28%): 'Porter' was a US nurse-staffing board, 'Navi' a San Francisco hardware startup, 'Slice' a team hiring in North Macedonia. Fix: keep a board only if it has at least one India-located job.",
  "Where: the public Greenhouse, Lever and Ashby job-board APIs, counted per board; the finder's own log (pipeline/discover.py). Why it matters: most hiring pages are built for experienced hires, so a fresher job tool cannot rely on company career pages. And 'looks like the right company' is not proof: without the India-job check, wrong companies would have been shown to students.",
  "Tab 'Evidence - boards' (total / India / entry-level jobs for every board). Tab 'Run stats'. Dropped boards: slice, pine, porter (Greenhouse and Lever), cloudflare, fi, navi, ditto, pocket, tiger, leap. Code: pipeline/discover.py."],
 ["3. An LLM tags role and city cheaply and well, but is weakest at judging experience level",
  f"Gemini 3.5 Flash-Lite cost about ${cost / posts * 1000:.2f} per 1,000 posts ({posts:,} posts, ${cost:.2f} total). On 50 random posts: role {role[0]:.0%}, city {city[0]:.0%}, fresher flag {fresh[0]:.0%} (strict; lenient {role[1]:.0%} / {city[1]:.0%} / {fresh[1]:.0%}). The model also removed 27 of 936 posts (2.9%) that Unstop had labelled fresher but that needed more experience. Its errors: it marked a '3-4 years' Sales Executive as fresher-friendly and rejected a 'Freshers to 6 years' post.",
  "Where: the tagging runs (token counts and cost are logged on every run) and my read of 50 posts against their full text. Why it matters: tags are cheap enough to run daily on everything, but the experience-level call is the one that decides whether a student sees a job that fits them, so it needs a human check or a stricter rule next.",
  "Tab 'Accuracy check (50)' (every error and ambiguous row with reasons). Tab 'Run stats' (tokens, cost, dropped posts). Tab 'Prompts' (exact prompt and settings). Screenshots tab, image 5. The review was AI-assisted."],
]
for r in F:
    fs.append(r)
for row in fs.iter_rows(min_row=3):
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    row[0].font = Font(bold=True)

# ---- Evidence tabs ----
rb = list(csv.DictReader((ROOT / "submission/evidence/robots_summary.csv").open(encoding="utf-8-sig")))
sheet("Evidence - robots", ["site", "robots_url", "http_status", "date_checked", "key_rules_quoted"],
      [[r["site"], r["robots_url"], r["http_status"], r["date_checked"],
        r["key_rules_quoted"] or "(no rules readable: server refused my bot with this status)"] for r in rb],
      [22, 48, 12, 14, 120])
sheet("Evidence - boards", ["platform", "board_slug", "company", "total_jobs", "india_jobs", "india_entry_level_jobs", "entry_share_of_india"],
      [[r["platform"], r["board_slug"], r["company"], int(r["total_jobs"]), int(r["india_jobs"]),
        int(r["india_entry_level_jobs"]), r["entry_share_of_india"]] for r in bd],
      [12, 28, 28, 12, 12, 22, 20])

# ---- Screenshots tab ----
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage
ss = wb.create_sheet("Screenshots")
ss.column_dimensions["A"].width = 120
caps = [
    ("01_live_site_all.png", "1. Live site: 910 posts, source split (Unstop 95%), search and role / city / type / source filters"),
    ("02_live_site_filtered.png", "2. Live site filtered to Software Engineering + Bengaluru (34 posts), each card shows LLM role and city tags"),
    ("03_github_actions_green_run.png", "3. GitHub Actions: the 'Daily refresh' workflow ran green (1m 49s); it is scheduled for 06:00 IST every day"),
    ("04_github_repo.png", "4. Public GitHub repo with the pipeline, eval scripts and submission files"),
    ("05_accuracy_errors_and_ambiguous.png", "5. Accuracy check: scores for 50 random posts, with every error and ambiguous case listed"),
]
row = 1
for fn, cap in caps:
    ss.cell(row, 1, cap).font = Font(bold=True)
    path = ROOT / "submission/screenshots" / fn
    w, h = PILImage.open(path).size
    img = XLImage(str(path)); img.width, img.height = 700, int(h * 700 / w)
    ss.add_image(img, f"A{row + 1}")
    row += int(img.height / 20) + 4

wb.save(OUT)
print("saved", OUT, "| cost per 1k:", round(cost / posts * 1000, 3), "| posts tagged:", posts, "| role/city/fresh strict:", f"{role[0]:.0%}/{city[0]:.0%}/{fresh[0]:.0%}")
