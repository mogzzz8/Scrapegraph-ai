"""
One-time setup: creates all required columns in the Job Search 2026 Notion database.
Run once via GitHub Actions (see .github/workflows/setup-notion.yml).
"""

import os
import sys
from notion_client import Client

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

client = Client(auth=NOTION_TOKEN)

properties = {
    # "Company" (Title) already exists — Notion creates it by default
    "Role": {
        "rich_text": {}
    },
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
                {"name": "LinkedIn",       "color": "blue"},
                {"name": "Wellfound",      "color": "orange"},
                {"name": "VC site",        "color": "purple"},
                {"name": "Cold outreach",  "color": "pink"},
                {"name": "Referral",       "color": "green"},
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

print(f"Setting up Notion database: {NOTION_DATABASE_ID}")
try:
    client.databases.update(
        database_id=NOTION_DATABASE_ID,
        properties=properties,
    )
    print("Done. All columns created successfully.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
