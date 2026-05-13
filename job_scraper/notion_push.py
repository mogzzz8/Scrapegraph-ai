"""
Push scraped job listings to a Notion database.
Handles deduplication and auto-creates the database if the given ID is a page.
"""

from datetime import date
from notion_client import Client

_STAGE_MAP = {
    "pre-seed": "Pre-seed", "preseed": "Pre-seed",
    "seed": "Seed",
    "series-a": "Series A", "series a": "Series A", "seriesa": "Series A",
    "series-b": "Series B+", "series b": "Series B+", "series b+": "Series B+",
}

_SOURCE_MAP = {
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

_DB_PROPERTIES = {
    "Company": {"title": {}},
    "Role":    {"rich_text": {}},
    "Stage": {"select": {"options": [
        {"name": "Pre-seed", "color": "purple"},
        {"name": "Seed",     "color": "blue"},
        {"name": "Series A", "color": "green"},
        {"name": "Series B+","color": "yellow"},
    ]}},
    "Source": {"select": {"options": [
        {"name": "LinkedIn",      "color": "blue"},
        {"name": "Wellfound",     "color": "orange"},
        {"name": "VC site",       "color": "purple"},
        {"name": "Cold outreach", "color": "pink"},
        {"name": "Referral",      "color": "green"},
    ]}},
    "Status": {"select": {"options": [
        {"name": "Sourced",   "color": "gray"},
        {"name": "Applied",   "color": "blue"},
        {"name": "Replied",   "color": "yellow"},
        {"name": "Screen",    "color": "orange"},
        {"name": "Interview", "color": "purple"},
        {"name": "Offer",     "color": "green"},
        {"name": "Rejected",  "color": "red"},
        {"name": "Ghosted",   "color": "default"},
    ]}},
    "Date applied":   {"date": {}},
    "Last touch":     {"date": {}},
    "Next action":    {"rich_text": {}},
    "Resume version": {"rich_text": {}},
    "Contact name":   {"rich_text": {}},
    "Notes":          {"rich_text": {}},
    "Salary range":   {"rich_text": {}},
    "Why I want it":  {"rich_text": {}},
}


def resolve_database_id(client: Client, given_id: str) -> str:
    """
    Given an ID that may be a page or a database:
    1. Try it as a database directly.
    2. If it's a page, look for a child database inside it.
    3. If none found, create the database inside the page.
    Returns the real database ID.
    """
    # Try as database
    try:
        client.databases.retrieve(database_id=given_id)
        print(f"  Notion database confirmed: {given_id}")
        return given_id
    except Exception as e:
        if "not a database" not in str(e).lower() and "validation" not in str(e).lower():
            raise

    # It's a page — look for a child database
    print("  Given ID is a page — searching for database inside it…")
    try:
        children = client.blocks.children.list(block_id=given_id)
        for block in children.get("results", []):
            if block.get("type") == "child_database":
                real_id = block["id"]
                print(f"  Found existing database: {real_id}")
                return real_id
    except Exception:
        pass

    # No database found — create one
    print("  No database found — creating Job Search 2026 database…")
    new_db = client.databases.create(
        parent={"type": "page_id", "page_id": given_id},
        title=[{"type": "text", "text": {"content": "Job Search 2026"}}],
        properties=_DB_PROPERTIES,
    )
    real_id = new_db["id"]
    print(f"  Database created: {real_id}")
    return real_id


def load_existing_jobs(client: Client, database_id: str) -> set:
    """Fetch all existing entries from Notion for deduplication."""
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
            title_prop = props.get("Company", {}).get("title", [])
            role_prop  = props.get("Role",    {}).get("rich_text", [])
            company = title_prop[0].get("plain_text", "").lower().strip() if title_prop else ""
            role    = role_prop[0].get("plain_text",  "").lower().strip() if role_prop  else ""
            if company and role:
                existing.add(f"{company}::{role}")
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return existing


def push_job(client: Client, database_id: str, job) -> bool:
    """Push a single RawJob to Notion. Returns True on success."""
    j = job.__dict__ if hasattr(job, "__dict__") else dict(job)
    today = date.today().isoformat()

    notes_parts = []
    if j.get("job_url"):
        notes_parts.append(f"URL: {j['job_url']}")
    if j.get("description_snippet"):
        notes_parts.append(j["description_snippet"])
    notes = "\n".join(notes_parts)[:2000]

    source_raw = j.get("source", "Wellfound")
    source = _SOURCE_MAP.get(source_raw, source_raw)
    valid_sources = {"LinkedIn", "Wellfound", "VC site", "Cold outreach", "Referral"}
    if source not in valid_sources:
        source = "Wellfound"

    stage_key = (j.get("stage") or "").lower().strip()
    stage = _STAGE_MAP.get(stage_key)

    properties: dict = {
        "Company": {"title": [{"text": {"content": (j.get("company") or "Unknown")[:100]}}]},
        "Role":    {"rich_text": [{"text": {"content": (j.get("title") or "")[:200]}}]},
        "Source":  {"select": {"name": source}},
        "Status":  {"select": {"name": "Sourced"}},
        "Last touch": {"date": {"start": today}},
    }
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}
    salary = (j.get("salary_range") or "").strip()
    if salary:
        properties["Salary range"] = {"rich_text": [{"text": {"content": salary[:200]}}]}
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
