"""
PLG App — POST /generate-leads route.
Wires the full qualification pipeline (Build Order Step 10.8).
"""

import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    GenerateLeadsRequest,
    GenerateLeadsResponse,
    ErrorResponse,
    JobStatus,
)
from app.pipeline.qualify import QualificationPipeline

logger = structlog.get_logger()

router = APIRouter(tags=["leads"])


@router.post(
    "/generate-leads",
    response_model=GenerateLeadsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad input"},
        500: {"model": ErrorResponse, "description": "Upstream failure"},
    },
)
async def generate_leads(request: GenerateLeadsRequest):
    """
    Trigger lead qualification pipeline.
    Synchronous mode: blocks until the sheet is ready (target < 90s).
    """
    job_id = str(uuid.uuid4())
    start = time.perf_counter()

    logger.info(
        "generate_leads_started",
        job_id=job_id,
        company_name=request.company_name,
        website=request.website,
    )

    # Validate required fields
    if not request.website.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error_code": "MISSING_WEBSITE",
                "message": "Website URL is required.",
            },
        )

    try:
        pipeline = QualificationPipeline()
        sheet_url, leads_count = await pipeline.run(
            company_name=request.company_name,
            website=request.website,
            lead_name=request.lead_name,
        )

        took = round(time.perf_counter() - start, 2)

        logger.info(
            "generate_leads_completed",
            job_id=job_id,
            took_seconds=took,
            leads_count=leads_count,
        )

        return GenerateLeadsResponse(
            status=JobStatus.COMPLETE,
            job_id=job_id,
            sheet_url=sheet_url,
            leads_count=leads_count,
            took_seconds=took,
        )

    except Exception as e:
        took = round(time.perf_counter() - start, 2)
        error_msg = str(e)
        logger.error(
            "generate_leads_failed",
            job_id=job_id,
            error=error_msg,
            took_seconds=took,
        )

        # Determine error code from the exception message
        if "LeadMagic" in error_msg or "leadmagic" in error_msg.lower():
            error_code = "LEADMAGIC_ERROR"
        elif "OpenRouter" in error_msg or "openrouter" in error_msg.lower():
            error_code = "AI_ERROR"
        elif "Google" in error_msg or "sheets" in error_msg.lower():
            error_code = "SHEETS_ERROR"
        else:
            error_code = "PIPELINE_ERROR"

        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error_code": error_code,
                "message": error_msg,
            },
        )
