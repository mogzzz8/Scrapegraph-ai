"""
One-time setup: creates all required columns in the Job Search 2026 Notion database.
Run once via GitHub Actions (see .github/workflows/setup-notion.yml).

Handles the case where NOTION_DATABASE_ID is actually a page ID (the table
lives inside the page) — it searches the page's children for the database.
"""

import os
import sys
from notion_client import Client

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

client = Client(auth=NOTION_TOKEN)

properties = {
    # "Company" (Title) already exists — Notion creates it by default
    "Role":           {"rich_text": {}},
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


def find_database_id(given_id: str) -> str:
    """
    Try the given ID as a database first. If Notion says it's a page,
    search that page's child blocks for the first database and return its ID.
    """
    # Try as database directly
    try:
        db = client.databases.retrieve(database_id=given_id)
        title = db.get("title", [{}])
        name = title[0].get("plain_text", "(untitled)") if title else "(untitled)"
        print(f"Found database directly: '{name}' ({given_id})")
        return given_id
    except Exception as e:
        err = str(e)
        if "not a database" not in err.lower() and "validation" not in err.lower():
            print(f"ERROR: {e}")
            sys.exit(1)

    # The ID is a page — look for a database inside it
    print(f"ID is a page, searching its children for a database…")
    try:
        children = client.blocks.children.list(block_id=given_id)
        for block in children.get("results", []):
            if block.get("type") == "child_database":
                db_id = block["id"]
                db_title = block.get("child_database", {}).get("title", "(untitled)")
                print(f"Found database inside page: '{db_title}' ({db_id})")
                return db_id
        print("ERROR: No database found inside the page. Make sure you added a Table to your Job Search 2026 page.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR reading page children: {e}")
        sys.exit(1)


print(f"Looking up Notion database (given ID: {NOTION_DATABASE_ID})…")
real_db_id = find_database_id(NOTION_DATABASE_ID)

print("Creating columns…")
try:
    client.databases.update(
        database_id=real_db_id,
        properties=properties,
    )
    print(f"Done. All 13 columns created successfully.")
    print(f"\nIMPORTANT: Update your NOTION_DATABASE_ID secret to: {real_db_id}")
except Exception as e:
    print(f"ERROR creating columns: {e}")
    sys.exit(1)
