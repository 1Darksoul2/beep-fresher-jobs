"""Collectors. Each returns a list of normalized post dicts:

{uid, source, title, company, location_raw, url, posted_at, type, description}
"""
import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config as C

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
INDIA = re.compile(C.INDIA_RE, re.I)
ENTRY_TITLE = re.compile(C.ENTRY_TITLE_RE, re.I)
ENTRY_DESC = re.compile(C.ENTRY_DESC_RE, re.I)
SENIOR = re.compile(C.SENIOR_TITLE_RE, re.I)


def clean_text(s: str) -> str:
    s = html.unescape(html.unescape(s or ""))
    s = _TAG_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def get_json(url: str, retries: int = 3):
    req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # network blips, 429s, 5xx
            if attempt == retries - 1:
                print(f"  ! failed {url}: {e}")
                return None
            time.sleep(2 ** attempt * 2)


def looks_entry_level(title: str, desc: str) -> bool:
    if SENIOR.search(title) and not re.search(r"intern|trainee", title, re.I):
        return False
    return bool(ENTRY_TITLE.search(title) or ENTRY_DESC.search(desc[:4000]))


# ---------------- Unstop (fresher-focused Indian platform) ----------------
def unstop() -> list[dict]:
    out = []
    for opp in ("jobs", "internships"):
        for page in range(1, C.UNSTOP_MAX_PAGES + 1):
            url = (
                "https://unstop.com/api/public/opportunity/search-result"
                f"?opportunity={opp}&page={page}&per_page={C.UNSTOP_PER_PAGE}&oppstatus=open"
            )
            d = get_json(url)
            time.sleep(C.REQUEST_DELAY_S)
            if not d:
                break
            items = d.get("data", {}).get("data", [])
            for x in items:
                jd = x.get("jobDetail") or {}
                filters = [f.get("name", "") for f in x.get("filters", []) if isinstance(f, dict)]
                max_exp = jd.get("max_experience")
                if opp == "jobs":
                    fresher_ok = "Fresher" in filters or (max_exp is not None and max_exp <= 2)
                    if not fresher_ok:
                        continue
                locs = [l.get("city") for l in (x.get("locations") or []) if l.get("city")]
                if not locs and jd.get("type") == "wfh":
                    locs = ["Remote (work from home)"]
                out.append({
                    "uid": f"unstop:{x['id']}",
                    "source": "Unstop",
                    "title": clean_text(x.get("title")),
                    "company": clean_text((x.get("organisation") or {}).get("name", "")),
                    "location_raw": ", ".join(locs),
                    "url": "https://unstop.com/" + x.get("public_url", ""),
                    "posted_at": x.get("approved_date") or x.get("updated_at"),
                    "type": "Internship" if opp == "internships" else "Job",
                    "description": clean_text(x.get("details"))[:3000],
                })
            if page >= d.get("data", {}).get("last_page", 0):
                break
    return out


# ---------------- Greenhouse / Lever / Ashby (public ATS APIs) ----------------
def _greenhouse(board: str) -> list[dict]:
    d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true") or {}
    out = []
    for x in d.get("jobs", []):
        out.append({
            "uid": f"gh:{board}:{x['id']}",
            "source": "Greenhouse",
            "title": clean_text(x.get("title")),
            "company": clean_text(x.get("company_name") or board),
            "location_raw": (x.get("location") or {}).get("name", ""),
            "url": x.get("absolute_url", ""),
            "posted_at": x.get("first_published") or x.get("updated_at"),
            "type": "Job",
            "description": clean_text(x.get("content"))[:3000],
        })
    return out


def _lever(board: str) -> list[dict]:
    d = get_json(f"https://api.lever.co/v0/postings/{board}?mode=json") or []
    out = []
    for x in d:
        cats = x.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location", "")]
        out.append({
            "uid": f"lever:{board}:{x['id']}",
            "source": "Lever",
            "title": clean_text(x.get("text")),
            "company": board.capitalize(),
            "location_raw": ", ".join(l for l in locs if l),
            "url": x.get("hostedUrl", ""),
            "posted_at": _ms_to_iso(x.get("createdAt")),
            "type": "Internship" if "intern" in (cats.get("commitment") or "").lower() else "Job",
            "description": clean_text(x.get("descriptionPlain") or x.get("description"))[:3000],
        })
    return out


def _ashby(board: str) -> list[dict]:
    d = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}") or {}
    out = []
    for x in d.get("jobs", []):
        out.append({
            "uid": f"ashby:{board}:{x['id']}",
            "source": "Ashby",
            "title": clean_text(x.get("title")),
            "company": board.capitalize(),
            "location_raw": x.get("location", ""),
            "url": x.get("jobUrl", ""),
            "posted_at": x.get("publishedAt"),
            "type": "Internship" if x.get("employmentType") == "Intern" else "Job",
            "description": clean_text(x.get("descriptionPlain"))[:3000],
        })
    return out


def _workable(board: str) -> list[dict]:
    d = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{board}?details=true") or {}
    out = []
    for x in d.get("jobs", []):
        locs = x.get("locations") or [{"city": x.get("city"), "country": x.get("country")}]
        loc = ", ".join(", ".join(v for v in (l.get("city"), l.get("country")) if v) for l in locs)
        if x.get("telecommuting"):
            loc = (loc + ", Remote").strip(", ")
        out.append({
            "uid": f"workable:{board}:{x.get('shortcode') or x.get('id')}",
            "source": "Workable",
            "title": clean_text(x.get("title")),
            "company": clean_text(d.get("name") or board),
            "location_raw": loc,
            "url": x.get("url") or x.get("shortlink") or x.get("application_url", ""),
            "posted_at": x.get("published_on") or x.get("created_at"),
            "type": "Internship" if "intern" in (x.get("employment_type") or "").lower() else "Job",
            "description": clean_text(x.get("description"))[:3000],
        })
    return out


def _ms_to_iso(ms):
    if not ms:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))


FETCHERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby, "workable": _workable}
# seconds between requests to the same host (Lever's robots.txt asks for Crawl-delay: 1)
HOST_DELAY = {"greenhouse": 0.3, "lever": 1.0, "ashby": 0.3, "workable": 0.5}


def load_boards() -> dict[str, list[str]]:
    """Boards found by pipeline/discover.py, merged with the hand-picked ones in config."""
    boards = {"greenhouse": set(C.GREENHOUSE_BOARDS), "lever": set(C.LEVER_BOARDS),
              "ashby": set(C.ASHBY_BOARDS), "workable": set()}
    f = Path(__file__).resolve().parent.parent / "data" / "boards.json"
    if f.exists():
        for platform, slugs in json.loads(f.read_text(encoding="utf-8"))["boards"].items():
            boards.setdefault(platform, set()).update(slugs)
    return {p: sorted(s) for p, s in boards.items()}


def _platform(platform: str, slugs: list[str]) -> list[dict]:
    """One platform at a time per host (polite), platforms in parallel."""
    out = []
    for s in slugs:
        for p in FETCHERS[platform](s):
            if INDIA.search(p["location_raw"]) and looks_entry_level(p["title"], p["description"]):
                out.append(p)
        time.sleep(HOST_DELAY[platform])
    return out


def ats() -> list[dict]:
    boards = load_boards()
    print("[collect] boards: " + ", ".join(f"{p}={len(s)}" for p, s in boards.items()))
    out = []
    with ThreadPoolExecutor(len(boards)) as ex:
        for posts in ex.map(lambda kv: _platform(*kv), boards.items()):
            out += posts
    return out


def collect_all() -> tuple[list[dict], dict]:
    stats = {}
    posts = []
    for name, fn in (("unstop", unstop), ("ats", ats)):
        t = time.time()
        got = fn()
        stats[name] = {"count": len(got), "seconds": round(time.time() - t, 1)}
        print(f"[collect] {name}: {len(got)} posts in {stats[name]['seconds']}s")
        posts += got
    return posts, stats
