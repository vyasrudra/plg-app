"""
PLG App — Pydantic request/response models.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from enum import Enum


# ─── Request Models ────────────────────────────────────────────

class GenerateLeadsRequest(BaseModel):
    """POST /generate-leads request body."""
    company_name: str = Field(..., min_length=1, description="Target company name")
    website: str = Field(..., min_length=1, description="Target company website URL")
    lead_name: Optional[str] = Field(default=None, description="Name of the lead/prospect")


# ─── Response Models ───────────────────────────────────────────

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"


class GenerateLeadsResponse(BaseModel):
    """POST /generate-leads response body."""
    status: JobStatus
    job_id: str
    sheet_url: Optional[str] = None
    leads_count: Optional[int] = None
    took_seconds: Optional[float] = None


class ErrorResponse(BaseModel):
    """Structured error response."""
    status: str = "error"
    error_code: str
    message: str


class StatusResponse(BaseModel):
    """GET /status/{job_id} response body."""
    status: JobStatus
    job_id: str
    sheet_url: Optional[str] = None
    leads_count: Optional[int] = None
    took_seconds: Optional[float] = None
    error_message: Optional[str] = None


# ─── Internal Models ───────────────────────────────────────────

class ICPProfile(BaseModel):
    """Extracted ICP from target website via Claude."""
    services_provided: list[str] = []
    niche: str = ""
    past_clients: list[str] = []


class QualifiedLead(BaseModel):
    """A single qualified lead ready for the Google Sheet."""
    company: str
    website: Optional[str] = None
    industry: Optional[str] = None
    employees: Optional[int] = None
    state: Optional[str] = None
    founded: Optional[str] = None
    relevance_score: int = 0
    why_qualified: str = ""
    buying_intent_signals: list[str] = []
    linkedin_url: Optional[str] = None


class CandidateCompany(BaseModel):
    """Raw company data from LeadMagic before qualification."""
    company_name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    state: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    founded_year: Optional[str] = None
    description: Optional[str] = None
    linkedin_url: Optional[str] = None
    ownership_status: Optional[str] = None
    revenue: Optional[float] = None
    revenue_formatted: Optional[str] = None
    total_funding: Optional[str] = None
    last_funding_round: Optional[str] = None
    last_funding_amount: Optional[float] = None
    last_funding_date: Optional[str] = None
