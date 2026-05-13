import os

# ── Notion ──────────────────────────────────────────────────────────────────
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

# ── LLM (used by ScrapeGraph AI for VC portfolio pages without central boards) ─
# Set ANTHROPIC_API_KEY in your shell, or paste it below.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Filters ─────────────────────────────────────────────────────────────────
# Soft filter: all Growth/Marketing roles in India — you decide what to apply to.
# Edit EXCLUDE_KEYWORDS to auto-skip anything you never want to see.
EXCLUDE_KEYWORDS = [
    "edtech", "ed-tech", "education technology",
    "tutoring", "e-learning", "upskill", "lms",
]

# ── Tier 1: Startup-specific job boards (highest signal) ────────────────────
# These are scraped with Playwright. Filter by Growth/Marketing in India.
JOB_BOARDS = {
    # Startup boards
    "Wellfound":      "https://wellfound.com/role/r/growth-manager?location_slug=india",
    "YC Startup Jobs":"https://www.ycombinator.com/jobs/role/growth?locations=India",
    "Cutshort":       "https://cutshort.io/jobs?q=growth+manager&location=india",
    "Instahyre":      "https://instahyre.com/search-jobs/?q=growth+manager&l=india",
    "Hirect":         "https://hirect.in/jobs?keyword=growth+manager&location=india",
    # Curated growth-specific
    "Lenny's Jobs":   "https://www.lennysjobs.com/growth",
    "Himalayas":      "https://himalayas.app/jobs/marketing?regions=Asia",
}

# ── Tier 2: VC centralized job boards ───────────────────────────────────────
# These aggregate roles across ALL portfolio companies — far more efficient
# than scraping individual company careers pages.
# All scraped the same way as JOB_BOARDS (Playwright + BS4).
VC_JOB_BOARDS = {
    "Peak XV":        "https://careers.peakxv.com/jobs",        # 400+ portfolio cos
    "Surge (Peak XV)":"https://careers.surge.peakxv.com/jobs",  # pre-seed/seed
    "Accel India":    "https://jobs.accel.com",
    "Lightspeed":     "https://jobs.lsvp.com",
    "Blume Ventures": "https://jobs.blume.vc/jobs",
    "Nexus VP":       "https://jobs.nexusvp.com",
    "Antler India":   "https://careers.antler.co/jobs",
}

# ── Tier 3: VC portfolio pages (ScrapeGraph AI two-step fallback) ────────────
# For VCs that don't have a centralized job board — ScrapeGraph finds portfolio
# company websites, then checks each company's /careers page.
VC_PORTFOLIO_PAGES = {
    "Kalaari Capital":  "https://www.kalaari.com/portfolio",
    "Stellaris VP":     "https://stellarisvp.com/portfolio",
    "Matrix India/Z47": "https://z47.com",
}

# Max portfolio companies to check per VC (keeps runtime reasonable)
MAX_COMPANIES_PER_VC = 15
