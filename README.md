# Fresher Jobs India

A live page listing fresher jobs and internships in India. Every day it collects posts from public sources, removes duplicates, uses an LLM to tag each post by role and city, and republishes the page on its own.

**Live:** https://1darksoul2.github.io/beep-fresher-jobs/ · **Data and prompts:** _add sheet link_

## Architecture

```
GitHub Actions (cron 06:00 IST)
  └─ python -m pipeline.run
       1. collect   pipeline/sources.py
            ├─ Unstop public API (jobs filtered to "Fresher" / ≤2 yrs, plus all internships)
            └─ Greenhouse / Lever / Ashby public job-board APIs
               (India location + entry-level title or "0-2 years" / "fresher" in the description)
       2. dedupe    pipeline/dedupe.py   uid → URL → normalized company|title|city → fuzzy title (≥0.92)
       3. tag       pipeline/tagger.py   Gemini 3.5 Flash-Lite, 20 posts per call,
                                         JSON schema with enum roles/cities, cached by post id
       4. publish   docs/data/jobs.json  + run stats (counts, tokens, cost)
  └─ commit → GitHub Pages serves docs/ (static HTML + JS search, no server)
```

Design choices:
- **Public APIs only.** Unstop's robots.txt explicitly allows `/api/public/*`. Greenhouse, Lever and Ashby job-board APIs are official endpoints meant for listing jobs. Every request uses an identifying User-Agent and waits 1 second between pages.
- **Enum-constrained output.** The schema limits role and city to fixed lists, so the model can't invent labels like "Bangalore Urban" and every output is valid JSON.
- **Tag cache.** Tags are saved by post id in `data/tags_cache.json`, so each daily run only pays for new posts.
- **LLM as a second filter.** The model also returns `is_fresher`. Posts the regex let through that actually need 2+ years of experience are dropped.

## Run locally

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...           # PowerShell: $env:GEMINI_API_KEY="..."  (free key: aistudio.google.com)
python -m pipeline.run              # or --no-llm to skip tagging
python -m http.server -d docs 8000  # open http://localhost:8000
```

## Accuracy and cost

```bash
python eval/make_sample.py   # writes eval/sample_50.csv (random, fixed seed)
# hand-check: fill correct_role / correct_city / correct_fresher only where the LLM is wrong
python eval/score.py
```

Cost is computed from real token usage on every run (input + output + thinking tokens, at paid-tier prices; the free tier costs $0). See `docs/data/last_run.json` → `tagging.cost_per_1000_posts_usd`.

Sample: 50 random posts (seed 20261118), each read against the full post text. "Clear error" = the tag is wrong. "Ambiguous" = a careful reader could defend either answer. **Strict** counts ambiguous as wrong, **lenient** counts it as right. The review was AI-assisted (see `eval/sample_50.csv`, columns `correct_*` / `ambiguous_*` / `notes`).

| Metric (n=50) | Strict | Lenient | Clear errors / ambiguous |
|---|---|---|---|
| Role | 94% | 100% | 0 / 3 |
| City | 92% | 100% | 0 / 4 |
| Fresher flag | 88% | 96% | 2 / 4 |
| Role and city both right | 86% | 100% | |

| Cost (paid tier, all runs combined) | |
|---|---|
| Posts tagged | 1,011 |
| Tokens in / out | 187,000 / 38,000 (thinking tokens: 0) |
| Total | about $0.16 |
| **Per 1,000 posts** | **about $0.15** (free tier: $0) |
| Steady-state daily cost | only new posts are tagged, usually well under $0.02 |

What the errors show:
- **Fresher flag is the weakest field.** It missed a "3-4 years" post and rejected a "Freshers to 6 years" post. Posts with a 1-3 year range are a judgment call.
- **City:** "Mohali" (next to Chandigarh) and posts with no stated location are forced into a bucket. A "Not stated" city would be cleaner.
- Only 3 of the 50 were predicted not-fresher, so recall on non-fresher posts is not well measured by this sample.

## Deploy

1. Push to GitHub. In **Settings → Secrets → Actions**, add `GEMINI_API_KEY`.
2. In **Settings → Pages**, set source to "Deploy from branch", branch `main`, folder `/docs`.
3. **Actions → Daily refresh → Run workflow** once to run it straight away.
