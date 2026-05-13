"""
Scrape VC portfolio pages for Growth/Marketing job openings.

Two-step process per VC:
  1. ScrapeGraph AI extracts the list of portfolio companies + their websites.
  2. For each company, ScrapeGraph AI checks /careers or /jobs for relevant roles.

Uses claude-3-5-haiku-20241022 (fast + cheap — ~$0.001 per page).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, Field

try:
    from scrapegraphai.graphs import SmartScraperGraph
    SCRAPEGRAPH_AVAILABLE = True
except ImportError:
    SCRAPEGRAPH_AVAILABLE = False


@dataclass
class RawJob:
    title: str
    company: str
    location: str = ""
    salary_range: str = ""
    job_url: str = ""
    description_snippet: str = ""
    stage: str = ""
    source: str = "VC site"


# ── Pydantic schemas for structured LLM extraction ───────────────────────────

class PortfolioCompany(BaseModel):
    name: str = Field(description="Company name")
    website: Optional[str] = Field(default=None, description="Company website URL (full https:// URL)")
    stage: Optional[str] = Field(default=None, description="Funding stage if mentioned: pre-seed, seed, series-a, series-b")


class PortfolioPage(BaseModel):
    companies: list[PortfolioCompany] = Field(description="All portfolio companies listed on this page")


class JobListing(BaseModel):
    title: str = Field(description="Exact job title")
    location: Optional[str] = Field(default=None, description="City/country or Remote")
    description_snippet: Optional[str] = Field(default=None, description="1-2 sentence summary of the role")
    job_url: Optional[str] = Field(default=None, description="Direct URL to apply for this job")


class CareersPage(BaseModel):
    jobs: list[JobListing] = Field(
        description="All Growth, Marketing, or Demand-Gen roles listed on this page. Empty list if none."
    )


# ── ScrapeGraph AI helpers ────────────────────────────────────────────────────

def _graph_config(api_key: str) -> dict:
    return {
        "llm": {
            "api_key": api_key,
            "model": "anthropic/claude-3-5-haiku-20241022",
        },
        "verbose": False,
        "headless": True,
    }


def _run_graph(prompt: str, url: str, schema, api_key: str):
    graph = SmartScraperGraph(
        prompt=prompt,
        source=url,
        schema=schema,
        config=_graph_config(api_key),
    )
    return graph.run()


def _get_portfolio_companies(vc_name: str, portfolio_url: str, api_key: str, max_companies: int) -> list[PortfolioCompany]:
    try:
        result = _run_graph(
            prompt=(
                "Extract every portfolio company listed on this page. "
                "For each company include its name, its website URL (the company's own site, not the VC's site), "
                "and its funding stage if mentioned."
            ),
            url=portfolio_url,
            schema=PortfolioPage,
            api_key=api_key,
        )
        companies = result.get("companies", []) if isinstance(result, dict) else []
        # Filter out entries without a usable website
        companies = [c for c in companies if c.get("website") and "http" in c.get("website", "")]
        return companies[:max_companies]
    except Exception as e:
        print(f"    Error fetching {vc_name} portfolio: {e}")
        return []


def _get_jobs_from_company(company_name: str, website: str, stage: str, api_key: str) -> list[RawJob]:
    careers_urls = [
        website.rstrip("/") + "/careers",
        website.rstrip("/") + "/jobs",
        website.rstrip("/") + "/work-with-us",
        website.rstrip("/") + "/join-us",
    ]

    for url in careers_urls:
        try:
            result = _run_graph(
                prompt=(
                    "Look for open job positions related to Growth, Marketing, Demand Generation, "
                    "or Revenue Marketing. For each role extract the job title, location, "
                    "a short description, and the URL to apply. "
                    "If the page has no relevant jobs, return an empty list."
                ),
                url=url,
                schema=CareersPage,
                api_key=api_key,
            )
            jobs_raw = result.get("jobs", []) if isinstance(result, dict) else []
            if jobs_raw:
                return [
                    RawJob(
                        title=j.get("title", ""),
                        company=company_name,
                        location=j.get("location", ""),
                        description_snippet=j.get("description_snippet", ""),
                        job_url=j.get("job_url", ""),
                        stage=stage or "",
                        source="VC site",
                    )
                    for j in jobs_raw if j.get("title")
                ]
        except Exception:
            continue   # try next URL pattern

    return []


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_vc_portfolios(vc_portfolio_pages: dict, api_key: str, max_companies: int = 15) -> list[RawJob]:
    if not SCRAPEGRAPH_AVAILABLE:
        print("  WARNING: scrapegraphai not installed — skipping VC portfolio scraping")
        return []
    if not api_key:
        print("  WARNING: ANTHROPIC_API_KEY not set — skipping VC portfolio scraping")
        return []

    all_jobs: list[RawJob] = []

    for vc_name, portfolio_url in vc_portfolio_pages.items():
        print(f"\n  {vc_name}:")
        companies = _get_portfolio_companies(vc_name, portfolio_url, api_key, max_companies)
        print(f"    {len(companies)} portfolio companies found")

        for company in companies:
            name = company.get("name", "")
            website = company.get("website", "")
            stage = company.get("stage", "")
            if not website:
                continue
            jobs = _get_jobs_from_company(name, website, stage, api_key)
            if jobs:
                print(f"    {name}: {len(jobs)} relevant role(s)")
                all_jobs.extend(jobs)

    return all_jobs
