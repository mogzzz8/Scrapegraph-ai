"""
One-time setup: creates the Job Search 2026 database (with all columns)
inside the Notion page, or updates it if it already exists.
Run once via GitHub Actions (see .github/workflows/setup-notion.yml).
"""

import os
import sys
from notion_client import Client

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
PAGE_ID = os.environ["NOTION_DATABASE_ID"]   # may be a page or a database ID

client = Client(auth=NOTION_TOKEN)

# All properties including the Title column (Company)
ALL_PROPERTIES = {
    "Company": {"title": {}},
    "Role":    {"rich_text": {}},
    "Stage": {
        "select": {
            "options": [
                {"name": "Pre-seed",  "color": "purple"},
                {"name": "Seed",      "color": "blue"},
                {"name": "Series A",  "color": "green"},
                {"name": "Series B+", "color": "yellow"},
            ]
        }
    },
    "Source": {
        "select": {
            "options": [
                {"name": "LinkedIn",      "color": "blue"},
                {"name": "Wellfound",     "color": "orange"},
                {"name": "VC site",       "color": "purple"},
                {"name": "Cold outreach", "color": "pink"},
                {"name": "Referral",      "color": "green"},
            ]
        }
    },
    "Status": {
        "select": {
            "options": [
                {"name": "Sourced",   "color": "gray"},
                {"name": "Applied",   "color": "blue"},
                {"name": "Replied",   "color": "yellow"},
                {"name": "Screen",    "color": "orange"},
                {"name": "Interview", "color": "purple"},
                {"name": "Offer",     "color": "green"},
                {"name": "Rejected",  "color": "red"},
                {"name": "Ghosted",   "color": "default"},
            ]
        }
    },
    "Date applied":   {"date": {}},
    "Last touch":     {"date": {}},
    "Next action":    {"rich_text": {}},
    "Resume version": {"rich_text": {}},
    "Contact name":   {"rich_text": {}},
    "Notes":          {"rich_text": {}},
    "Salary range":   {"rich_text": {}},
    "Why I want it":  {"rich_text": {}},
}

# Properties for update (exclude Title — can't update title type)
UPDATE_PROPERTIES = {k: v for k, v in ALL_PROPERTIES.items() if k != "Company"}


def find_existing_database(page_id: str):
    """Return the database ID if a child_database exists inside page_id, else None."""
    try:
        children = client.blocks.children.list(block_id=page_id)
        for block in children.get("results", []):
            if block.get("type") == "child_database":
                return block["id"]
    except Exception:
        pass
    return None


def try_as_database(given_id: str):
    """Return given_id if it's already a valid database, else None."""
    try:
        client.databases.retrieve(database_id=given_id)
        return given_id
    except Exception:
        return None


print(f"Looking up Notion page / database…")

# 1. Check if the given ID is already a database
real_db_id = try_as_database(PAGE_ID)

# 2. Check if there's a database inside the page
if not real_db_id:
    real_db_id = find_existing_database(PAGE_ID)
    if real_db_id:
        print(f"Found existing database inside page: {real_db_id}")

# 3. No database found — create one inside the page
if not real_db_id:
    print("No database found — creating Job Search 2026 database inside the page…")
    try:
        new_db = client.databases.create(
            parent={"type": "page_id", "page_id": PAGE_ID},
            title=[{"type": "text", "text": {"content": "Job Search 2026"}}],
            properties=ALL_PROPERTIES,
        )
        real_db_id = new_db["id"]
        print(f"Database created successfully!")
        print(f"\n>>> UPDATE YOUR SECRET <<<")
        print(f"Go to GitHub → Settings → Secrets → Actions")
        print(f"Update NOTION_DATABASE_ID to: {real_db_id}")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR creating database: {e}")
        sys.exit(1)

# 4. Database exists — update its columns
print(f"Updating columns on existing database: {real_db_id}")
try:
    client.databases.update(
        database_id=real_db_id,
        properties=UPDATE_PROPERTIES,
    )
    print("Done. All 13 columns created successfully.")
    print(f"\n>>> UPDATE YOUR SECRET <<<")
    print(f"Go to GitHub → Settings → Secrets → Actions")
    print(f"Update NOTION_DATABASE_ID to: {real_db_id}")
except Exception as e:
    print(f"ERROR updating columns: {e}")
    sys.exit(1)
