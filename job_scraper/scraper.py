#!/usr/bin/env python3
"""
Job Scraper — Amog's Monday morning sourcing run.

Three-tier scraping:
  Tier 1 — Startup job boards (Wellfound, YC, Cutshort, Instahyre, Hirect,
            Lenny's, Himalayas) — Playwright + BS4
  Tier 2 — VC centralized job boards (Peak XV, Accel, Lightspeed, Blume,
            Nexus, Antler) — same Playwright + BS4, scrapes ALL portfolio roles
  Tier 3 — VCs without central boards (Kalaari, Stellaris, Z47) —
            ScrapeGraph AI two-step (portfolio page → individual company /careers)

Results are deduped and pushed to the Job Search 2026 Notion database.

Run:
    python scraper.py              # full run (all three tiers)
    python scraper.py --boards     # Tier 1 only
    python scraper.py --vc-boards  # Tier 2 only (VC centralized boards)
    python scraper.py --vc-pages   # Tier 3 only (ScrapeGraph AI, requires API key)
    python scraper.py --dry-run    # print matches, don't push to Notion
"""

import argparse
import json
import os
import sys
from datetime import date
from notion_client import Client

# Add parent dir so we can import scrapegraphai when running from this folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scrapers.job_boards import scrape_all_boards
from scrapers.vc_pages import scrape_vc_portfolios
from notion_push import push_job

# Tier 2 VC boards use the same Playwright scraper as Tier 1 job boards —
# they're already aggregated, so we just point it at different URLs.
# Source label is overridden to "VC site" in notion_push.py mapping.

SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_jobs.json")


# ── Deduplication ─────────────────────────────────────────────────────────────

def _load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def _save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def _job_key(job) -> str:
    j = job.__dict__ if hasattr(job, "__dict__") else dict(job)
    company = (j.get("company") or "").lower().strip()
    title = (j.get("title") or "").lower().strip()
    return f"{company}::{title}"


# ── Filtering ─────────────────────────────────────────────────────────────────

def _is_excluded(job) -> bool:
    j = job.__dict__ if hasattr(job, "__dict__") else dict(job)
    text = " ".join([
        j.get("title", ""), j.get("company", ""), j.get("description_snippet", "")
    ]).lower()
    return any(kw in text for kw in config.EXCLUDE_KEYWORDS)


# ── Main ──────────────────────────────────────────────────────────────────────

def run(do_boards: bool, do_vc_boards: bool, do_vc_pages: bool, dry_run: bool):
    print("=" * 55)
    print(f"  Job Scraper  |  {date.today()}")
    print("=" * 55)

    notion = Client(auth=config.NOTION_TOKEN)
    seen = _load_seen()
    added, skipped, excluded = 0, 0, 0
    all_jobs = []

    # ── Tier 1: startup job boards ────────────────────────────────────────────
    if do_boards:
        print("\n[Tier 1] Startup job boards")
        board_jobs = scrape_all_boards(config.JOB_BOARDS)
        all_jobs.extend(board_jobs)

    # ── Tier 2: VC centralized job boards ────────────────────────────────────
    if do_vc_boards:
        print("\n[Tier 2] VC centralized job boards")
        vc_board_jobs = scrape_all_boards(config.VC_JOB_BOARDS)
        # Tag source as "VC site"
        for job in vc_board_jobs:
            job.source = "VC site"
        all_jobs.extend(vc_board_jobs)

    # ── Tier 3: VC portfolio pages (ScrapeGraph AI) ───────────────────────────
    if do_vc_pages:
        print("\n[Tier 3] VC portfolio pages (ScrapeGraph AI)")
        vc_jobs = scrape_vc_portfolios(
            config.VC_PORTFOLIO_PAGES,
            api_key=config.ANTHROPIC_API_KEY,
            max_companies=config.MAX_COMPANIES_PER_VC,
        )
        all_jobs.extend(vc_jobs)

    # ── 3. Filter + push ──────────────────────────────────────────────────────
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Pushing to Notion…")
    for job in all_jobs:
        key = _job_key(job)

        if key in seen:
            skipped += 1
            continue

        if _is_excluded(job):
            j = job.__dict__ if hasattr(job, "__dict__") else dict(job)
            print(f"  Excluded (keyword match): {j.get('company')} — {j.get('title')}")
            excluded += 1
            seen.add(key)
            continue

        j = job.__dict__ if hasattr(job, "__dict__") else dict(job)
        label = f"  {j.get('company') or '?':30s} | {j.get('title') or '?'}"

        if dry_run:
            print(f"  [DRY RUN] would add: {label}")
            seen.add(key)
            added += 1
        else:
            ok = push_job(notion, config.NOTION_DATABASE_ID, job)
            if ok:
                seen.add(key)
                added += 1
                print(f"  Added: {label}")

    _save_seen(seen)

    print("\n" + "=" * 55)
    print(f"  Added: {added}  |  Skipped (duplicate): {skipped}  |  Excluded: {excluded}")
    print("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape jobs → Notion")
    parser.add_argument("--boards",    action="store_true", help="Tier 1: startup job boards only")
    parser.add_argument("--vc-boards", action="store_true", help="Tier 2: VC centralized job boards only")
    parser.add_argument("--vc-pages",  action="store_true", help="Tier 3: VC portfolio pages (ScrapeGraph AI, needs API key)")
    parser.add_argument("--dry-run",   action="store_true", help="Print matches, skip Notion push")
    args = parser.parse_args()

    any_flag = args.boards or args.vc_boards or args.vc_pages
    run(
        do_boards=args.boards    or not any_flag,
        do_vc_boards=args.vc_boards or not any_flag,
        do_vc_pages=args.vc_pages  or not any_flag,
        dry_run=args.dry_run,
    )
