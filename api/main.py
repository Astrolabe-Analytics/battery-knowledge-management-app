"""
Astrolabe Research Library — FastAPI Backend

This API wraps the existing lib/ modules to provide HTTP endpoints
for the React frontend.

Usage:
    uvicorn api.main:app --reload --port 8002
"""
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import settings, discover, imports

# Route modules (PostgreSQL-backed)
from api.routes import papers, search, collections, history

app = FastAPI(
    title="Astrolabe Research Library API",
    version="0.1.0",
    description="Backend API for the Astrolabe paper management and RAG system",
)

# CORS — configurable via CORS_ORIGINS env var (comma-separated)
# In production behind nginx (same-origin proxy), CORS is not needed
# but we keep it for dev and direct-access scenarios.
_default_origins = [
    "http://localhost:5173",  # Vite default
    "http://localhost:5174",  # Vite fallback
    "http://localhost:3000",  # CRA fallback
]
_cors_env = os.environ.get("CORS_ORIGINS", "")
cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "astrolabe-api"}
