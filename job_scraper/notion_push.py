"""
Push scraped job listings to a Notion database.

Maps RawJob fields to the Job Search 2026 schema defined in plan.md.
Fields the user fills manually (Date applied, Next action, Resume version,
Contact name, Why I want it) are left blank — don't invent them.
"""

from datetime import date
from notion_client import Client

# Valid select option names must match what you created in Notion exactly.
VALID_STAGES = {"Pre-seed", "Seed", "Series A", "Series B+"}
VALID_SOURCES = {"LinkedIn", "Wellfound", "VC site", "Cold outreach", "Referral", "Peerlist", "Instahyre", "Hirect"}

_STAGE_MAP = {
    "pre-seed": "Pre-seed", "preseed": "Pre-seed",
    "seed": "Seed",
    "series-a": "Series A", "series a": "Series A", "seriesa": "Series A",
    "series-b": "Series B+", "series b": "Series B+", "series b+": "Series B+",
}


def _normalise_stage(raw: str) -> str | None:
    if not raw:
        return None
    return _STAGE_MAP.get(raw.lower().strip())


def _normalise_source(raw: str) -> str:
    if raw in VALID_SOURCES:
        return raw
    # Map board names that aren't in the original schema
    overrides = {"Peerlist": "Wellfound", "Instahyre": "Wellfound", "Hirect": "Wellfound"}
    return overrides.get(raw, "Wellfound")


def push_job(client: Client, database_id: str, job) -> bool:
    """
    Push a single RawJob (dataclass or dict) to Notion.
    Returns True on success, False on failure.
    """
    if hasattr(job, "__dict__"):
        j = job.__dict__
    else:
        j = dict(job)

    today = date.today().isoformat()

    # Notes field: URL first, then description snippet
    notes_parts = []
    if j.get("job_url"):
        notes_parts.append(f"URL: {j['job_url']}")
    if j.get("description_snippet"):
        notes_parts.append(j["description_snippet"])
    notes = "\n".join(notes_parts)[:2000]  # Notion rich-text limit

    properties: dict = {
        "Company": {
            "title": [{"text": {"content": (j.get("company") or "Unknown")[:100]}}]
        },
        "Role": {
            "rich_text": [{"text": {"content": (j.get("title") or "")[:200]}}]
        },
        "Source": {
            "select": {"name": _normalise_source(j.get("source", "Wellfound"))}
        },
        "Status": {
            "select": {"name": "Sourced"}
        },
        "Last touch": {
            "date": {"start": today}
        },
    }

    if notes:
        properties["Notes"] = {
            "rich_text": [{"text": {"content": notes}}]
        }

    salary = j.get("salary_range", "").strip()
    if salary:
        properties["Salary range"] = {
            "rich_text": [{"text": {"content": salary[:200]}}]
        }

    stage = _normalise_stage(j.get("stage", ""))
    if stage:
        properties["Stage"] = {"select": {"name": stage}}

    try:
        client.pages.create(
            parent={"database_id": database_id},
            properties=properties,
        )
        return True
    except Exception as e:
        print(f"    Notion push failed for {j.get('company')} / {j.get('title')}: {e}")
        return False
