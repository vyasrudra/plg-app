"""
PLG App — Google Sheets service.
Adds a new tab to a shared template spreadsheet for each lead list.
Uses a service account — no OAuth flow, no file creation (avoids SA quota limits).
"""

import base64
import json
import time
from datetime import datetime
from typing import Optional

import structlog
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.models.schemas import QualifiedLead

logger = structlog.get_logger()

# Sheet columns per PRD Section 6, Step 6
SHEET_HEADERS = [
    "Company",
    "Website",
    "Industry",
    "Employees",
    "State",
    "Founded",
    "Relevance Score",
    "Why Qualified",
    "Buying Intent Signals",
    "LinkedIn URL",
    "Contact Name",
    "Contact Title",
    "Contact Email",
    "Contact Phone"
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Template spreadsheet ID — lives in the shared folder, owned by the user
TEMPLATE_SHEET_ID = "1GkzADhz5Mx6CzhEOHl0Yhc90AukFFG0OtYabQNuq_e8"


class GoogleSheetsClient:
    """Google Sheets client that writes lead lists as new tabs in a shared template."""

    def __init__(self):
        settings = get_settings()
        self.folder_id = settings.google_drive_folder_id

        # Decode base64 service account credentials
        creds_json = settings.google_credentials_json
        try:
            decoded = base64.b64decode(creds_json)
            creds_info = json.loads(decoded)
        except Exception:
            creds_info = json.loads(creds_json)

        credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        self.sheets_service = build("sheets", "v4", credentials=credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)

    def create_sheet(self, target_company: str, leads: list[QualifiedLead]) -> str:
        """
        Create a new tab in the template spreadsheet with qualified leads.
        Returns a direct URL to the new tab.

        This avoids creating new Drive files (SA has 0 quota).
        Each lead list becomes a separate tab in the shared template.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        tab_name = f"{target_company[:30]} — {timestamp}"

        start = time.perf_counter()

        # 1. Add a new sheet tab
        add_result = self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=TEMPLATE_SHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": tab_name,
                                "index": 0,  # Insert at the front
                            }
                        }
                    }
                ]
            },
        ).execute()
        new_sheet_id = add_result["replies"][0]["addSheet"]["properties"]["sheetId"]

        # 2. Write header row + data
        rows = [SHEET_HEADERS]
        for lead in leads:
            rows.append([
                lead.company,
                lead.website or "",
                lead.industry or "",
                lead.employees if lead.employees is not None else "",
                lead.state or "",
                lead.founded or "",
                lead.relevance_score,
                lead.why_qualified,
                ", ".join(lead.buying_intent_signals),
                lead.linkedin_url or "",
                lead.contact_name or "",
                lead.contact_title or "",
                lead.contact_email or "",
                lead.contact_phone or "",
            ])

        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=TEMPLATE_SHEET_ID,
            range=f"'{tab_name}'!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        # 3. Format header row (bold white text on dark background + freeze)
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": new_sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.15, "green": 0.15, "blue": 0.25},
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            },
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": new_sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Auto-resize columns to fit content
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": new_sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": len(SHEET_HEADERS),
                    }
                }
            },
        ]
        self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=TEMPLATE_SHEET_ID,
            body={"requests": requests},
        ).execute()

        # 4. Ensure the spreadsheet is publicly readable
        try:
            self.drive_service.permissions().create(
                fileId=TEMPLATE_SHEET_ID,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except Exception:
            # Permission might already exist — that's fine
            pass

        # URL with gid pointing directly to the new tab
        sheet_url = (
            f"https://docs.google.com/spreadsheets/d/{TEMPLATE_SHEET_ID}"
            f"/edit#gid={new_sheet_id}"
        )

        duration = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "sheet_created",
            spreadsheet_id=TEMPLATE_SHEET_ID,
            tab=tab_name,
            rows=len(leads),
            duration_ms=duration,
        )

        return sheet_url
