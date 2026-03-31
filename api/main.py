"""
Astrolabe Research Library — FastAPI Backend

This API wraps the existing lib/ modules to provide HTTP endpoints
for the React frontend.

Usage:
    uvicorn api.main:app --reload --port 8002
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from api.routes import settings, discover, imports

# Route modules (PostgreSQL-backed)
from api.routes import papers, search, collections, history, system

app = FastAPI(
    title="Astrolabe Research Library API",
    version="0.1.0",
    description="Backend API for the Astrolabe paper management and RAG system",
)

# CORS — allow Vite dev server in local development.
# In production the frontend is served from the same origin, so CORS isn't
# needed, but keeping these origins here doesn't hurt.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Vite fallback port
        "http://localhost:8003",  # single-container local
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route groups
app.include_router(papers.router, prefix="/api/papers", tags=["Papers"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(collections.router, prefix="/api/collections", tags=["Collections"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(discover.router, prefix="/api/discover", tags=["Discover"])
app.include_router(imports.router, prefix="/api/import", tags=["Import"])
app.include_router(system.router, prefix="/api/system", tags=["System"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "astrolabe-api"}


# Serve React SPA — must be mounted AFTER all /api routes.
# In production (Docker) ./dist exists. In local dev the Vite dev server
# runs separately so this silently no-ops when dist/ is absent.
_dist = os.path.join(os.path.dirname(__file__), "..", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
