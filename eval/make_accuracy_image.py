"""Render eval/sample_50.csv review as a screenshot-ready page -> submission/screenshots/05_accuracy_errors_and_ambiguous.png
(uses Microsoft Edge headless; Windows path below)."""
import csv, html, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
rows = list(csv.DictReader((ROOT / "eval/sample_50.csv").open(encoding="utf-8-sig")))
n = len(rows)

def sc(k):
    c = sum(1 for r in rows if r[f"correct_{k}"].strip())
    a = sum(1 for r in rows if r[f"ambiguous_{k}"].strip() and not r[f"correct_{k}"].strip())
    return f"{(n - c - a) / n:.0%}", f"{(n - c) / n:.0%}", c, a

flag = []
for i, r in enumerate(rows, 1):
    if not r["notes"].strip():
        continue
    kind = "ERROR" if r["notes"].startswith("ERROR") else "AMBIGUOUS"
    segs = [s.split(": ", 1)[-1] for s in r["notes"].split(" | ")]
    fields = [k for k in ("role", "city", "fresher") if r[f"correct_{k}"].strip() or r[f"ambiguous_{k}"].strip()]
    for j, k in enumerate(fields):
        llm = r["llm_is_fresher"] if k == "fresher" else r[f"llm_{k}"]
        flag.append((i, r["title"][:44], r["company"][:26], k, llm, r[f"correct_{k}"] or r[f"ambiguous_{k}"],
                     kind if r[f"correct_{k}"].strip() else "AMBIGUOUS", segs[min(j, len(segs) - 1)]))
flag.sort(key=lambda x: (x[6] != "ERROR", x[0]))
body = "".join(
    f"<tr class='{x[6].lower()}'><td>{x[0]}</td><td>{html.escape(x[1])}<br><small>{html.escape(x[2])}</small></td>"
    f"<td>{x[3]}</td><td>{html.escape(str(x[4]))}</td><td>{html.escape(str(x[5]))}</td><td><b>{x[6]}</b></td><td>{html.escape(x[7])}</td></tr>"
    for x in flag)
R, C, F = sc("role"), sc("city"), sc("fresher")
page = f"""<!doctype html><meta charset=utf-8><style>
body{{font:14px/1.45 Segoe UI,Arial,sans-serif;margin:24px;color:#16181d;background:#fff}}h1{{font-size:20px;margin:0 0 4px}}
.s{{display:flex;gap:12px;margin:14px 0}}.b{{border:1px solid #ddd;border-radius:8px;padding:10px 14px}}.b big{{font-size:22px;font-weight:700;display:block}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px 8px;vertical-align:top;text-align:left}}th{{background:#1f4e79;color:#fff}}
.error td{{background:#fdecea}}.ambiguous td{{background:#fff8e1}}small{{color:#666}}</style>
<h1>Tagging accuracy: 50 random posts (seed 20261118)</h1>
<div>Each post read against its full text. Strict = ambiguous counted wrong. Lenient = ambiguous counted right. AI-assisted review.</div>
<div class=s><div class=b>Role<big>{R[0]} / {R[1]}</big>{R[2]} errors, {R[3]} ambiguous</div><div class=b>City<big>{C[0]} / {C[1]}</big>{C[2]} errors, {C[3]} ambiguous</div><div class=b>Fresher flag<big>{F[0]} / {F[1]}</big>{F[2]} errors, {F[3]} ambiguous</div><div class=b>Cost<big>~$0.15 / 1,000 posts</big>gemini-3.5-flash-lite, paid prices</div></div>
<table><tr><th>#</th><th>Post</th><th>Field</th><th>LLM said</th><th>Should be</th><th>Type</th><th>Why</th></tr>{body}</table>"""
tmp = Path(tempfile.gettempdir()) / "accuracy_page.html"
tmp.write_text(page, encoding="utf-8")
out = ROOT / "submission/screenshots/05_accuracy_errors_and_ambiguous.png"
height = 330 + 62 * len(flag)
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size=1250,{height}",
                f"--screenshot={out}", tmp.as_uri()], capture_output=True, timeout=120)
print("wrote", out, "rows:", len(flag))
