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

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.auth import require_auth
from api.routes import settings, discover, imports, auth

# Route modules (PostgreSQL-backed)
from api.routes import papers, search, collections, history, citations
from api.routes import reactions

app = FastAPI(
    title="Astrolabe Research Library API",
    version="0.1.0",
    description="Backend API for the Astrolabe paper management and RAG system",
)


# Strip trailing slashes so nginx + FastAPI don't create redirect loops.
# Nginx may append a slash; FastAPI redirect_slashes would 307 it back off.
class TrailingSlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.scope["path"]
        if path != "/" and path.endswith("/"):
            request.scope["path"] = path.rstrip("/")
        return await call_next(request)

# CORS — configurable via CORS_ORIGINS env var (comma-separated)
# In production behind nginx (same-origin proxy), CORS is not needed
# but we keep it for dev and direct-access scenarios.
_default_origins = [
    "http://localhost:5173",  # Vite default
    "http://localhost:5174",  # Vite fallback
    "http://localhost:3000",  # CRA fallback
    "http://192.168.0.154:5173",  # Local network (phone access)
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

app.add_middleware(TrailingSlashMiddleware)

# ── Public routes (no auth required) ────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

# ── Protected routes (auth required when AUTH_PASSWORD is set) ──
_auth = [Depends(require_auth)]
app.include_router(papers.router, prefix="/api/papers", tags=["Papers"], dependencies=_auth)
app.include_router(search.router, prefix="/api/search", tags=["Search"], dependencies=_auth)
app.include_router(collections.router, prefix="/api/collections", tags=["Collections"], dependencies=_auth)
app.include_router(history.router, prefix="/api/history", tags=["History"], dependencies=_auth)
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"], dependencies=_auth)
app.include_router(discover.router, prefix="/api/discover", tags=["Discover"], dependencies=_auth)
app.include_router(imports.router, prefix="/api/import", tags=["Import"], dependencies=_auth)
app.include_router(citations.router, prefix="/api/citations", tags=["Citations"], dependencies=_auth)
app.include_router(reactions.router, prefix="/api/reactions", tags=["Reactions"], dependencies=_auth)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "astrolabe-api"}
