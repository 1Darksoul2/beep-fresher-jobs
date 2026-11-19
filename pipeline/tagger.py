"""LLM tagging with Google Gemini (JSON-schema output, batched, cached).

Each call tags TAG_BATCH_SIZE posts. Output is constrained to a JSON schema whose
role/city fields are enums, so the model can't invent labels.
Tags are cached by uid in data/tags_cache.json, so the daily run only pays for NEW posts.
"""
import json
import time

from google import genai
from google.genai import types

from . import config as C

SYSTEM_PROMPT = f"""You label Indian job and internship posts for a student career platform.

For every post, return:
- role: the single best-fitting function from this list: {json.dumps(C.ROLES)}
  Judge by what the person will actually do day to day, not by buzzwords.
  "Business Analyst" doing reporting/SQL -> Data Science & Analytics. "SDE"/"Developer" -> Software Engineering.
  ML/LLM/GenAI building roles -> AI / Machine Learning. Telecalling / inside sales -> Sales & Business Development.
- city: the primary work city from this list: {json.dumps(C.CITIES)}
  Map aliases: Bangalore -> Bengaluru; Gurgaon/Gurugram/Noida/New Delhi/Faridabad/Ghaziabad -> Delhi NCR;
  Navi Mumbai/Thane -> Mumbai; Secunderabad -> Hyderabad; Trivandrum -> Thiruvananthapuram.
  Work-from-home with no office city -> Remote. Two or more different cities -> Multiple.
  An Indian city not in the list -> Other India.
- is_fresher: true if a fresh graduate or current student could get it (internship, trainee,
  0-1 or 0-2 years of experience, or no experience requirement stated). false if it needs 2+ years.

Return one result per post, using the post's id exactly as given."""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "role": {"type": "string", "enum": C.ROLES},
                    "city": {"type": "string", "enum": C.CITIES},
                    "is_fresher": {"type": "boolean"},
                },
                "required": ["id", "role", "city", "is_fresher"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _post_block(i: int, p: dict) -> str:
    return (
        f"<post id=\"{i}\">\n"
        f"title: {p['title']}\ncompany: {p['company']}\ntype: {p['type']}\n"
        f"location: {p['location_raw'] or 'not stated'}\n"
        f"description: {p['description'][:C.DESC_CHARS]}\n</post>"
    )


class Tagger:
    def __init__(self):
        # reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment
        self.client = genai.Client()
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
            thinking_config=types.ThinkingConfig(thinking_level=C.THINKING_LEVEL),
            max_output_tokens=8000,
        )
        self.usage = {"calls": 0, "posts": 0, "input_tokens": 0, "output_tokens": 0,
                      "thinking_tokens": 0, "failed_batches": 0}

    def _call(self, prompt: str):
        for attempt in range(4):
            try:
                return self.client.models.generate_content(model=C.MODEL, contents=prompt, config=self.config)
            except Exception as e:  # 429 on free tier / transient 5xx
                if attempt == 3:
                    raise
                wait = 15 * (attempt + 1)
                print(f"  ! {type(e).__name__}: {str(e)[:120]} -- retrying in {wait}s")
                time.sleep(wait)

    def _tag_batch(self, batch: list[dict]) -> dict[str, dict]:
        prompt = "Label these posts:\n\n" + "\n\n".join(_post_block(i, p) for i, p in enumerate(batch))
        resp = self._call(prompt)
        um = resp.usage_metadata
        self.usage["calls"] += 1
        self.usage["input_tokens"] += um.prompt_token_count or 0
        self.usage["output_tokens"] += um.candidates_token_count or 0
        self.usage["thinking_tokens"] += um.thoughts_token_count or 0
        results = json.loads(resp.text)["results"]
        out = {}
        for r in results:
            try:
                p = batch[int(r["id"])]
            except (ValueError, IndexError):
                continue
            if r["role"] not in C.ROLES or r["city"] not in C.CITIES:
                continue  # schema enums should prevent this; never trust, always check
            out[p["uid"]] = {"role": r["role"], "city": r["city"], "is_fresher": r["is_fresher"],
                             "model": C.MODEL}
        return out

    def tag(self, posts: list[dict], cache: dict) -> dict:
        todo = [p for p in posts if p["uid"] not in cache]
        print(f"[tag] {len(posts) - len(todo)} cached, {len(todo)} new to tag")
        for start in range(0, len(todo), C.TAG_BATCH_SIZE):
            batch = todo[start:start + C.TAG_BATCH_SIZE]
            try:
                got = self._tag_batch(batch)
            except Exception as e:
                # one retry with smaller batches so one weird post can't sink 20
                print(f"  ! batch failed ({e}); retrying in halves")
                got = {}
                for half in (batch[: len(batch) // 2], batch[len(batch) // 2:]):
                    try:
                        got.update(self._tag_batch(half))
                    except Exception as e2:
                        print(f"  ! half failed: {e2}")
                        self.usage["failed_batches"] += 1
            cache.update(got)
            self.usage["posts"] += len(got)
            print(f"  tagged {min(start + C.TAG_BATCH_SIZE, len(todo))}/{len(todo)}")
            time.sleep(C.SECONDS_BETWEEN_CALLS)
        return cache

    def cost_report(self) -> dict:
        u = self.usage
        # Gemini bills thinking tokens at the output rate
        billed_out = u["output_tokens"] + u["thinking_tokens"]
        cost = u["input_tokens"] / 1e6 * C.PRICE_IN_PER_M + billed_out / 1e6 * C.PRICE_OUT_PER_M
        per_1k = cost / u["posts"] * 1000 if u["posts"] else None
        return {**u, "model": C.MODEL, "cost_usd": round(cost, 5),
                "cost_per_1000_posts_usd": round(per_1k, 4) if per_1k else None}
