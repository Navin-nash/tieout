"""FastAPI application — ``uvicorn tieout.api.app:app``."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tieout.api.routes import router

app = FastAPI(
    title="Tieout API",
    description="JSON API consumed by the dashboard (SPEC section 12, ADR-003).",
    version="0.1.0",
)
app.include_router(router)


@app.exception_handler(Exception)
async def safe_errors(_request: Request, exc: Exception) -> JSONResponse:
    """No stack traces, paths or secrets in error responses."""
    if isinstance(exc, ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
