"""Auth routes — login and token validation."""

import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.auth import AUTH_PASSWORD, auth_enabled, create_token, verify_token

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Authenticate with the shared company password."""
    if not auth_enabled():
        # No password set — return a dummy token (dev mode)
        return LoginResponse(token="dev-mode", message="Auth disabled — no password set")

    if not hmac.compare_digest(req.password, AUTH_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_token()
    return LoginResponse(token=token, message="Login successful")


@router.get("/check")
async def check_auth():
    """Check if auth is enabled. Public endpoint (no token needed)."""
    return {"auth_enabled": auth_enabled()}
