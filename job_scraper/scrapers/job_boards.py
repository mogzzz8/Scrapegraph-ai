"""
Scrape structured job boards (Wellfound, Peerlist, Instahyre, Hirect).

Strategy: Playwright headless browser → BeautifulSoup parsing.
Each site section tries site-specific selectors first, then falls back
to generic heuristics so the script degrades gracefully if a site redesigns.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class RawJob:
    title: str
    company: str
    location: str = ""
    salary_range: str = ""
    job_url: str = ""
    description_snippet: str = ""
    stage: str = ""
    source: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _text(el) -> str:
    return el.get_text(separator=" ", strip=True) if el else ""


def _first(soup, *selectors) -> Optional[object]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el
    return None


def _abs_url(href: str, base: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    from urllib.parse import urljoin
    return urljoin(base, href)


# ── Page fetcher ──────────────────────────────────────────────────────────────

async def _fetch_page(url: str, wait_selector: str = None, timeout: int = 20000) -> str:
    """Render a page with Playwright and return HTML."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=8000)
                except Exception:
                    pass
            await page.wait_for_timeout(3000)   # let JS finish rendering
            return await page.content()
        except Exception as e:
            print(f"    fetch error for {url}: {e}")
            return ""
        finally:
            await browser.close()


# ── Site-specific parsers ─────────────────────────────────────────────────────

def _parse_wellfound(html: str, base_url: str) -> list[RawJob]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Wellfound wraps each role in a div with data-test="StartupResult"
    # or a <div class="...styles_component...">; fall back to generic cards.
    cards = soup.select("[data-test='StartupResult']")
    if not cards:
        cards = soup.select("div[class*='styles_jobResult'], div[class*='JobResult']")
    if not cards:
        # Last-resort: any block containing an <a> with /jobs/ in href
        cards = [a.parent for a in soup.find_all("a", href=re.compile(r"/jobs/"))]

    for card in cards:
        title_el = _first(card,
            "h2", "[data-test='job-title']", "a[class*='title']",
            "span[class*='title']", "div[class*='role']",
        )
        company_el = _first(card,
            "[data-test='startup-name']", "a[class*='company']",
            "span[class*='company']", "div[class*='startup']",
        )
        loc_el = _first(card,
            "[data-test='location']", "span[class*='location']",
            "div[class*='location']",
        )
        link = card.find("a", href=re.compile(r"/jobs/|/role/"))
        salary_el = _first(card, "span[class*='comp']", "div[class*='salary']")

        title = _text(title_el)
        company = _text(company_el)
        if not title or not company:
            continue

        jobs.append(RawJob(
            title=title,
            company=company,
            location=_text(loc_el),
            salary_range=_text(salary_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="Wellfound",
        ))
    return jobs


def _parse_peerlist(html: str, base_url: str) -> list[RawJob]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.select("div[class*='job'], article[class*='job'], li[class*='job']")
    if not cards:
        cards = soup.select("a[href*='/jobs/']")
        cards = list({c.parent for c in cards})

    for card in cards:
        title_el = _first(card, "h3", "h2", "strong", "p[class*='title']")
        company_el = _first(card, "p[class*='company']", "span[class*='company']", "p")
        loc_el = _first(card, "span[class*='loc']", "div[class*='loc']")
        link = card.find("a", href=True)

        title = _text(title_el)
        if not title:
            continue
        company = _text(company_el) if company_el and company_el != title_el else ""

        jobs.append(RawJob(
            title=title,
            company=company,
            location=_text(loc_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="Peerlist",
        ))
    return jobs


def _parse_instahyre(html: str, base_url: str) -> list[RawJob]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.select("div.job-card, div[class*='jobCard'], div[class*='job-item']")
    if not cards:
        cards = soup.select("div[class*='card']")

    for card in cards:
        title_el = _first(card, "h2", "h3", "a[class*='title']", "div[class*='title']")
        company_el = _first(card, "div[class*='company']", "span[class*='company']", "p[class*='company']")
        loc_el = _first(card, "span[class*='location']", "div[class*='location']")
        salary_el = _first(card, "span[class*='salary']", "div[class*='ctc']")
        link = card.find("a", href=True)

        title = _text(title_el)
        if not title:
            continue

        jobs.append(RawJob(
            title=title,
            company=_text(company_el),
            location=_text(loc_el),
            salary_range=_text(salary_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="Instahyre",
        ))
    return jobs


def _parse_hirect(html: str, base_url: str) -> list[RawJob]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.select("div[class*='job'], div[class*='card'], article")
    for card in cards:
        title_el = _first(card, "h2", "h3", "strong", "div[class*='title']")
        company_el = _first(card, "div[class*='company']", "span[class*='company']")
        loc_el = _first(card, "span[class*='loc']", "div[class*='loc']")
        link = card.find("a", href=True)

        title = _text(title_el)
        if not title:
            continue

        jobs.append(RawJob(
            title=title,
            company=_text(company_el),
            location=_text(loc_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="Hirect",
        ))
    return jobs


def _parse_getro(html: str, base_url: str) -> list[RawJob]:
    """
    Getro-powered boards: Peak XV, Accel, Blume, Nexus, Antler, Lightspeed.
    Getro renders job cards with class patterns like 'JobCard' or 'job-card'.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.select("[class*='JobCard'], [class*='job-card'], [class*='jobCard']")
    if not cards:
        # Getro sometimes uses <li> wrappers
        cards = soup.select("li[class*='job'], li[class*='Job']")
    if not cards:
        cards = soup.select("div[class*='position'], div[class*='role']")

    for card in cards:
        title_el = _first(card, "h3", "h2", "[class*='title']", "[class*='name']", "strong")
        company_el = _first(card, "[class*='company']", "[class*='org']", "span")
        loc_el = _first(card, "[class*='location']", "[class*='loc']")
        link = card.find("a", href=True)

        title = _text(title_el)
        if not title:
            continue

        jobs.append(RawJob(
            title=title,
            company=_text(company_el),
            location=_text(loc_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="VC site",
        ))
    return jobs


def _parse_yc(html: str, base_url: str) -> list[RawJob]:
    """YC Work at a Startup — React app with Next.js data."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # YC embeds structured data in a <script id="__NEXT_DATA__"> tag
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        import json as _json
        try:
            data = _json.loads(next_data.string)
            listings = (
                data.get("props", {})
                    .get("pageProps", {})
                    .get("jobListings", [])
                or data.get("props", {})
                    .get("pageProps", {})
                    .get("jobs", [])
            )
            for item in listings:
                title = item.get("title") or item.get("job_title", "")
                company = item.get("company_name") or item.get("company", {}).get("name", "")
                location = item.get("location") or item.get("job_location", "")
                url = item.get("url") or item.get("absolute_url", "")
                if title:
                    jobs.append(RawJob(
                        title=title, company=company, location=location,
                        job_url=url, source="YC Startup Jobs",
                    ))
            if jobs:
                return jobs
        except Exception:
            pass

    # Fallback: generic card parsing
    cards = soup.select("div[class*='job'], div[class*='listing'], tr[class*='job']")
    for card in cards:
        title_el = _first(card, "h3", "h2", "td[class*='title']", "a[class*='title']")
        company_el = _first(card, "td[class*='company']", "div[class*='company']")
        title = _text(title_el)
        if title:
            link = card.find("a", href=True)
            jobs.append(RawJob(
                title=title,
                company=_text(company_el),
                job_url=_abs_url(link["href"] if link else "", base_url),
                source="YC Startup Jobs",
            ))
    return jobs


def _parse_lenny(html: str, base_url: str) -> list[RawJob]:
    """Lenny's Job Board."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    cards = soup.select("div[class*='job'], article, div[class*='listing']")
    for card in cards:
        title_el = _first(card, "h2", "h3", "strong", "div[class*='title']")
        company_el = _first(card, "div[class*='company']", "span[class*='company']", "p")
        loc_el = _first(card, "span[class*='loc']", "div[class*='loc']")
        link = card.find("a", href=True)
        title = _text(title_el)
        if not title:
            continue
        jobs.append(RawJob(
            title=title, company=_text(company_el), location=_text(loc_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="Lenny's Jobs",
        ))
    return jobs


def _parse_himalayas(html: str, base_url: str) -> list[RawJob]:
    """Himalayas remote jobs board."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    cards = soup.select("div[class*='job'], article[class*='job'], li[class*='job']")
    if not cards:
        cards = soup.select("[data-job], [class*='JobCard']")
    for card in cards:
        title_el = _first(card, "h3", "h2", "[class*='title']")
        company_el = _first(card, "[class*='company']", "span")
        loc_el = _first(card, "[class*='location']")
        salary_el = _first(card, "[class*='salary']", "[class*='comp']")
        link = card.find("a", href=True)
        title = _text(title_el)
        if not title:
            continue
        jobs.append(RawJob(
            title=title, company=_text(company_el), location=_text(loc_el),
            salary_range=_text(salary_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="Himalayas",
        ))
    return jobs


def _parse_cutshort(html: str, base_url: str) -> list[RawJob]:
    """Cutshort.io — AI-matched startup jobs."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    cards = soup.select("div[class*='job'], div[class*='card'], div[class*='result']")
    for card in cards:
        title_el = _first(card, "h2", "h3", "[class*='title']", "a[class*='title']")
        company_el = _first(card, "[class*='company']", "span[class*='org']")
        loc_el = _first(card, "[class*='location']", "[class*='loc']")
        salary_el = _first(card, "[class*='salary']", "[class*='ctc']")
        link = card.find("a", href=True)
        title = _text(title_el)
        if not title:
            continue
        jobs.append(RawJob(
            title=title, company=_text(company_el), location=_text(loc_el),
            salary_range=_text(salary_el),
            job_url=_abs_url(link["href"] if link else "", base_url),
            source="Cutshort",
        ))
    return jobs


# Getro-powered boards (Peak XV, Accel, Blume, Nexus, Antler, Lightspeed, Surge)
_GETRO_BOARDS = {"Peak XV", "Surge (Peak XV)", "Accel India", "Lightspeed", "Blume Ventures", "Nexus VP", "Antler India"}

PARSERS = {
    "Wellfound":       (_parse_wellfound, "div[class*='styles'], [data-test]"),
    "YC Startup Jobs": (_parse_yc,        "div[class*='job']"),
    "Cutshort":        (_parse_cutshort,  "div[class*='job']"),
    "Peerlist":        (_parse_peerlist,  "div[class*='job']"),
    "Instahyre":       (_parse_instahyre, "div[class*='job']"),
    "Hirect":          (_parse_hirect,    "div[class*='job']"),
    "Lenny's Jobs":    (_parse_lenny,     "div[class*='job']"),
    "Himalayas":       (_parse_himalayas, "div[class*='job']"),
    # VC centralized boards (all Getro-powered)
    "Peak XV":         (_parse_getro,     "[class*='JobCard']"),
    "Surge (Peak XV)": (_parse_getro,     "[class*='JobCard']"),
    "Accel India":     (_parse_getro,     "[class*='JobCard']"),
    "Lightspeed":      (_parse_getro,     "[class*='JobCard']"),
    "Blume Ventures":  (_parse_getro,     "[class*='JobCard']"),
    "Nexus VP":        (_parse_getro,     "[class*='JobCard']"),
    "Antler India":    (_parse_getro,     "[class*='JobCard']"),
}


# ── Public API ────────────────────────────────────────────────────────────────

async def scrape_board_async(name: str, url: str) -> list[RawJob]:
    print(f"  Scraping {name}…")
    parser_fn, wait_sel = PARSERS.get(name, (_parse_wellfound, None))
    html = await _fetch_page(url, wait_selector=wait_sel)
    if not html:
        print(f"    No HTML returned for {name}")
        return []
    jobs = parser_fn(html, url)
    print(f"    Found {len(jobs)} listings on {name}")
    return jobs


def scrape_all_boards(job_boards: dict) -> list[RawJob]:
    """Synchronous wrapper — runs all board scrapers in sequence."""
    if not PLAYWRIGHT_AVAILABLE:
        print("  WARNING: playwright not installed — skipping job board scraping")
        return []

    all_jobs = []
    for name, url in job_boards.items():
        jobs = asyncio.run(scrape_board_async(name, url))
        all_jobs.extend(jobs)
    return all_jobs
