"""
PLG App — Google Sheets service.
Creates sheets, writes rows, sets public read access.
Uses a service account — no OAuth flow.
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
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsClient:
    """Google Sheets + Drive client for creating and sharing lead sheets."""

    def __init__(self):
        settings = get_settings()
        self.folder_id = settings.google_drive_folder_id

        # Decode base64 service account credentials
        creds_json = settings.google_credentials_json
        try:
            decoded = base64.b64decode(creds_json)
            creds_info = json.loads(decoded)
        except Exception:
            # Try as raw JSON string
            creds_info = json.loads(creds_json)

        credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        self.sheets_service = build("sheets", "v4", credentials=credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)

    def create_sheet(self, target_company: str, leads: list[QualifiedLead]) -> str:
        """
        Create a new Google Sheet with qualified leads.
        Returns the public URL.
        """
        title = f"Leads for {target_company} — {datetime.now().strftime('%Y-%m-%d')}"

        start = time.perf_counter()

        # 1. Create the spreadsheet
        spreadsheet_body = {
            "properties": {"title": title},
            "sheets": [{"properties": {"title": "Qualified Leads"}}],
        }
        spreadsheet = (
            self.sheets_service.spreadsheets()
            .create(body=spreadsheet_body)
            .execute()
        )
        spreadsheet_id = spreadsheet["spreadsheetId"]

        # 2. Move to the designated Drive folder
        file = self.drive_service.files().get(
            fileId=spreadsheet_id, fields="parents"
        ).execute()
        previous_parents = ",".join(file.get("parents", []))
        self.drive_service.files().update(
            fileId=spreadsheet_id,
            addParents=self.folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()

        # 3. Set public read access
        self.drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()

        # 4. Write header row + data
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
            ])

        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Qualified Leads!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        # 5. Format header row (bold + freeze)
        requests = [
            {
                "repeatCell": {
                    "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.3},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": 0, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]
        self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit?usp=sharing"

        duration = round((time.perf_counter() - start) * 1000, 1)
        logger.info("sheet_created", spreadsheet_id=spreadsheet_id, rows=len(leads), duration_ms=duration)

        return sheet_url
