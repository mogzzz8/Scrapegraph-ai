"""
Push scraped job listings to a Notion database.
Also handles deduplication by querying existing entries at run start.

Maps RawJob fields to the Job Search 2026 schema defined in plan.md.
Fields the user fills manually (Date applied, Next action, Resume version,
Contact name, Why I want it) are left blank — don't invent them.
"""

from datetime import date
from notion_client import Client

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
    overrides = {
        "Peerlist": "Wellfound", "Instahyre": "Wellfound",
        "Hirect": "Wellfound", "YC Startup Jobs": "Wellfound",
        "Lenny's Jobs": "Wellfound", "Himalayas": "Wellfound",
        "Cutshort": "Wellfound",
        "Peak XV": "VC site", "Surge (Peak XV)": "VC site",
        "Accel India": "VC site", "Lightspeed": "VC site",
        "Blume Ventures": "VC site", "Nexus VP": "VC site",
        "Antler India": "VC site", "Kalaari Capital": "VC site",
        "Stellaris VP": "VC site", "Matrix India/Z47": "VC site",
    }
    return overrides.get(raw, "Wellfound")


def load_existing_jobs(client: Client, database_id: str) -> set:
    """
    Fetch all existing entries from Notion and return a set of
    'company::title' keys for deduplication.
    Handles pagination automatically.
    """
    existing = set()
    cursor = None
    while True:
        kwargs = {"database_id": database_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        try:
            response = client.databases.query(**kwargs)
        except Exception as e:
            print(f"  Warning: could not load existing Notion entries: {e}")
            break

        for page in response.get("results", []):
            props = page.get("properties", {})
            company = ""
            role = ""
            title_prop = props.get("Company", {}).get("title", [])
            if title_prop:
                company = title_prop[0].get("plain_text", "").lower().strip()
            role_prop = props.get("Role", {}).get("rich_text", [])
            if role_prop:
                role = role_prop[0].get("plain_text", "").lower().strip()
            if company and role:
                existing.add(f"{company}::{role}")

        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return existing


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

    notes_parts = []
    if j.get("job_url"):
        notes_parts.append(f"URL: {j['job_url']}")
    if j.get("description_snippet"):
        notes_parts.append(j["description_snippet"])
    notes = "\n".join(notes_parts)[:2000]

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

