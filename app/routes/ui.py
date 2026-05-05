"""
PLG App — GET / (HTMX testing page).
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter(tags=["ui"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def testing_ui(request: Request):
    """Serve the HTMX testing page for manual trigger and result preview."""
    return templates.TemplateResponse("index.html", {"request": request})
