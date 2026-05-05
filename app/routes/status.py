"""
PLG App — GET /status/{job_id} route.
Only needed if async path is built later.
"""

from fastapi import APIRouter

from app.models.schemas import StatusResponse, JobStatus

router = APIRouter(tags=["status"])


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_job_status(job_id: str):
    """
    Check status of a lead generation job.
    Currently a stub — returns complete since we're running synchronously.
    """
    return StatusResponse(
        status=JobStatus.COMPLETE,
        job_id=job_id,
        sheet_url=None,
        leads_count=None,
        took_seconds=None,
        error_message=None,
    )
