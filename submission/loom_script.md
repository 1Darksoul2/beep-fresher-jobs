# Loom script (target 4:45, face + screen)

Say it in your own words. This is a skeleton, not something to read out. They said "the thinking has to be yours."

## 0:00 – 0:25  What I built (face on camera, then live site on screen)
- "I built a live page of fresher jobs and internships in India. It has about 900 posts from 650 companies, de-duplicated, tagged by role and city with an LLM, and it refreshes itself every morning at 6 AM IST."
- Open https://1darksoul2.github.io/beep-fresher-jobs/ . Type "python" in search, filter City = Bengaluru, Role = Software Engineering, click the Source filter.

## 0:25 – 1:30  Architecture (screen: README diagram or the repo)
1. **Collect** (`pipeline/sources.py`): Unstop's public API (its robots.txt explicitly allows `/api/public/*`) plus company careers pages through the public Greenhouse, Lever and Ashby job-board APIs.
2. **De-duplicate** (`pipeline/dedupe.py`): four layers: same id, same URL, same cleaned company + title + city, then fuzzy title match at 0.92. This run removed 33 of 967.
3. **Tag** (`pipeline/tagger.py`): Gemini 3.5 Flash-Lite, 20 posts per call, JSON-schema output, role and city restricted to fixed lists so it can't invent labels. It also returns `is_fresher`, so I can drop posts that need 2+ years.
4. **Cache**: tags are stored by post id, so each daily run only pays for new posts.
5. **Publish**: GitHub Actions runs at 6 AM IST, commits `jobs.json`, GitHub Pages serves a static page. No server, no database, nothing to pay for.
- Show `.github/workflows/daily.yml` and the green run in the Actions tab.

## 1:30 – 3:15  What broke and how I fixed it (the part they care about)
1. **Which sites I could use.** I checked robots.txt and terms first. Naukri, Indeed, Glassdoor, LinkedIn and Internshala block automated access, and SmartRecruiters' API blocks everyone but LinkedIn. I left them out on purpose. Cost: Unstop is 95% of posts and I say that openly on the page.
2. **Company finder matched the wrong companies.** I guess a board name from the company name. "Porter" matched a US nurse-staffing board, "Navi" a San Francisco hardware startup, "Slice" a North Macedonia team. Fix: a board is only kept if it has at least one India-located job. That dropped 11 wrong boards.
3. **Gemini returned "503 overloaded" a lot.** The first full tagging run took 31 minutes instead of about 5. Fix: retries with increasing waits, and if a batch still fails it is split in half. Zero posts were lost. Next step I would add: automatic switch to a backup model.
4. **Only 87 of 812 India jobs on company boards were entry-level**, because companies like Stripe and Databricks hire senior people in India. So the company boards add fewer posts than I expected. Unstop is built for students, so that is where the volume is.
5. **Source text has broken characters** (a few Unstop titles contain "�"). That is in the source data. I haven't cleaned it yet.

## 3:15 – 4:15  The numbers (screen: the workbook's Summary tab)
- 50 random posts (fixed seed), each read against the full post text.
- **Role 94% strict / 100% lenient. City 92% / 100%. Fresher flag 88% / 96%.** "Strict" counts a debatable call as wrong.
- Errors worth naming: it marked a "3-4 years experience" Sales Executive as fresher-friendly, and rejected a post saying "Freshers to 6 years". City: "Mohali" next to Chandigarh and posts with no location get forced into a bucket. I'd add a "Not stated" city.
- Be upfront on camera about how you checked: "I used Claude to do a first pass and I verified [X rows] myself." Only say what is true.
- **Cost: about $0.15 per 1,000 posts** at paid prices (1,011 posts, $0.16 total), $0 on Google's free tier. Daily cost is a few cents at most because only new posts are tagged.

## 4:15 – 4:45  What I'd do next
- Add a "Not stated" city and a small second pass for posts where the fresher flag is borderline.
- Backup model for the 503 case.
- More sources that allow it (Adzuna or Jooble APIs) to get Unstop below 80%.
- Offer to change anything live.

---

# If they ask you to change it live on the 30-minute call

| They ask | Where to change | Time |
|---|---|---|
| Add or rename a role | `ROLES` in `pipeline/config.py` (the schema and prompt read this list automatically) | 2 min, then re-run tagging (delete `data/tags_cache.json` to re-tag everything) |
| Add a city | `CITIES` in `pipeline/config.py` | 2 min |
| Add a company | add a line to `data/companies.txt`, run `python -m pipeline.discover` | 3 min |
| Add a new source | add a function in `pipeline/sources.py` returning the same dict shape, add it to `collect_all()` | 10 min |
| Change what counts as "fresher" | the `is_fresher` rule in `SYSTEM_PROMPT` in `pipeline/tagger.py`, and `ENTRY_TITLE_RE` in `config.py` | 3 min |
| Change the look or add a filter | `docs/index.html`, `docs/app.js` (see how the Source filter was added) | 5 min |
| Show salary / stipend | Unstop returns `min_salary`/`max_salary` in `jobDetail`: add to the dict in `sources.py`, then `app.js` | 10 min |

Run locally: `python -m pipeline.run` (needs `GEMINI_API_KEY` in `.env`), or `--no-llm` to skip tagging. Preview: `python -m http.server -d docs 8000`.
