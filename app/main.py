"""
PLG App — FastAPI entrypoint.
Health check, structured logging, and route registration.
"""

import time
import uuid

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import generate, status, ui

# ─── Structured Logging Setup ──────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if True else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# ─── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="PLG — Personalised Lead Generator",
    description="AI-powered B2B lead qualification service. Takes a prospect's company info, outputs 50 hyper-qualified leads in a Google Sheet.",
    version="1.0.0",
)

# ─── Middleware: request_id + timing ───────────────────────────

@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ─── Routes ────────────────────────────────────────────────────

app.include_router(generate.router)
app.include_router(status.router)
app.include_router(ui.router)


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint for deployment verification."""
    return {"status": "healthy", "service": "plg-app", "version": "1.0.0"}


# ─── Run ───────────────────────────────────────────────────────

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )
