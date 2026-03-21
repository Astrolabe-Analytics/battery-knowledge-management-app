"""
Simple shared-password authentication for Astrolabe.

Uses HMAC-signed tokens (no external dependencies).
Everyone logs in with the same company-wide password set via AUTH_PASSWORD env var.
"""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException, Request


# ── Configuration ────────────────────────────────────────
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")
AUTH_SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", AUTH_PASSWORD + "-astrolabe-secret")
TOKEN_EXPIRY_DAYS = 30


def auth_enabled() -> bool:
    """Auth is only enforced when AUTH_PASSWORD is set."""
    return bool(AUTH_PASSWORD)


# ── Token helpers ────────────────────────────────────────
def create_token() -> str:
    """Create an HMAC-signed token with expiry."""
    payload = {"exp": int(time.time()) + TOKEN_EXPIRY_DAYS * 24 * 3600}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(
        AUTH_SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> bool:
    """Verify an HMAC-signed token."""
    parts = token.split(".")
    if len(parts) != 2:
        return False
    payload_b64, sig = parts
    expected = hmac.new(
        AUTH_SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return False
    return payload.get("exp", 0) > time.time()


# ── FastAPI dependency ───────────────────────────────────
async def require_auth(request: Request):
    """Dependency that enforces authentication when AUTH_PASSWORD is set."""
    if not auth_enabled():
        return  # No password configured → open access (dev mode)

    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if verify_token(token):
            return

    # Check query param (for PDF viewer / download links)
    token_param = request.query_params.get("token")
    if token_param and verify_token(token_param):
        return

    raise HTTPException(status_code=401, detail="Authentication required")
