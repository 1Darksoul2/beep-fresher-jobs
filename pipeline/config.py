"""Central config: sources, taxonomy, model, pricing."""
import os

# ---- LLM ----
MODEL = os.environ.get("TAGGER_MODEL", "gemini-3.5-flash-lite")
THINKING_LEVEL = os.environ.get("TAGGER_THINKING", "low")   # labeling needs little reasoning
# Paid-tier USD per 1M tokens for gemini-3.5-flash-lite (ai.google.dev pricing, Nov 2026).
# Output price includes thinking tokens. Free tier costs $0 but has rate limits.
PRICE_IN_PER_M = float(os.environ.get("PRICE_IN_PER_M", 0.30))
PRICE_OUT_PER_M = float(os.environ.get("PRICE_OUT_PER_M", 2.50))
SECONDS_BETWEEN_CALLS = 4.5  # stays under free-tier requests-per-minute limits
TAG_BATCH_SIZE = 20          # posts per LLM call
DESC_CHARS = 700             # description chars sent to the LLM per post

# ---- Politeness ----
USER_AGENT = "BeepFresherJobsBot/1.0 (student project; public APIs only)"
REQUEST_DELAY_S = 1.0        # sleep between requests to the same host

# ---- Sources ----
# Unstop: robots.txt explicitly allows /api/public/*
UNSTOP_MAX_PAGES = 12        # x 50 posts per page, per opportunity type
UNSTOP_PER_PAGE = 50

# Public ATS job-board APIs (official, documented, meant for embedding job lists)
GREENHOUSE_BOARDS = [
    "groww", "razorpaysoftwareprivatelimited", "inmobi", "hackerrank", "gitlab",
    "stripe", "okta", "mongodb", "elastic", "pubmatic", "druva", "databricks", "twilio",
]
LEVER_BOARDS = ["cred", "zeta", "meesho", "paytm", "nium"]
ASHBY_BOARDS = ["sarvam"]

# ---- Taxonomy (the LLM must pick from these) ----
ROLES = [
    "Software Engineering",
    "Data Science & Analytics",
    "AI / Machine Learning",
    "Product Management",
    "Design (UI/UX/Graphic)",
    "Marketing & Growth",
    "Sales & Business Development",
    "Customer Support & Success",
    "Finance & Accounting",
    "HR & Recruiting",
    "Operations & Supply Chain",
    "Content & Writing",
    "Consulting & Strategy",
    "Core Engineering (Mech/Civil/Electrical)",
    "Legal & Compliance",
    "Other",
]

CITIES = [
    "Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Pune", "Chennai", "Kolkata",
    "Ahmedabad", "Jaipur", "Chandigarh", "Indore", "Kochi", "Coimbatore", "Lucknow",
    "Bhubaneswar", "Nagpur", "Surat", "Vadodara", "Thiruvananthapuram", "Visakhapatnam",
    "Other India", "Remote", "Multiple",
]

INDIA_RE = (
    r"india|bengaluru|bangalore|mumbai|pune|delhi|gurugram|gurgaon|noida|hyderabad|"
    r"chennai|kolkata|ahmedabad|jaipur|chandigarh|indore|kochi|coimbatore|lucknow|"
    r"bhubaneswar|nagpur|surat|vadodara|thiruvananthapuram|trivandrum|visakhapatnam"
)
ENTRY_TITLE_RE = (
    r"\b(intern|internship|trainee|graduate|fresher|entry[- ]level|junior|jr\.?|"
    r"associate|apprentice|campus|new grad|sde ?-?\s?(1|i)|engineer ?(1|i)|analyst)\b"
)
ENTRY_DESC_RE = (
    r"\b(0\s*(-|–|to)\s*[12]\+?\s*(years|yrs)|freshers?|recent graduates?|new graduates?|"
    r"final[- ]year|batch of 202[5-7]|202[5-7] (batch|graduates?))\b"
)
SENIOR_TITLE_RE = r"\b(senior|sr\.?|staff|principal|lead|head|director|manager|vp|architect)\b"
