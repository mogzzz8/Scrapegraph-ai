"""
One-time setup: creates all required columns in the Job Search 2026 Notion database.
Run once via GitHub Actions (see .github/workflows/setup-notion.yml).
"""

import os
import sys
from notion_client import Client
from notion_client.errors import APIResponseError

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

print(f"Connecting to Notion database: {NOTION_DATABASE_ID}")

# Step 1: verify we can reach the database at all
try:
    db = client.databases.retrieve(database_id=NOTION_DATABASE_ID)
    print(f"Database found: {db.get('title', [{}])[0].get('plain_text', '(untitled)')}")
except APIResponseError as e:
    print(f"\nERROR reaching database: {e.code} — {e.message}")
    if e.code == "object_not_found":
        print(
            "\nFix: The Notion integration is not connected to this database.\n"
            "In Notion, open the 'Job Search 2026' page → tap '...' (top right)\n"
            "→ Connections → Add connection → select your integration."
        )
    elif e.code == "unauthorized":
        print("\nFix: The NOTION_TOKEN secret is incorrect. Check it in GitHub Settings → Secrets.")
    sys.exit(1)

# Step 2: create the columns
print("Creating columns…")
try:
    client.databases.update(
        database_id=NOTION_DATABASE_ID,
        properties=properties,
    )
    print("Done. All 13 columns created successfully.")
except APIResponseError as e:
    print(f"\nERROR creating columns: {e.code} — {e.message}")
    sys.exit(1)
