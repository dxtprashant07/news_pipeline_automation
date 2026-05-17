"""API key authentication dependency for the editor dashboard."""
from fastapi import Header, HTTPException, status
from core.config.settings import get_settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency — validates X-API-Key header.

    Auth is skipped when DASHBOARD_API_KEY is not set (local dev only).
    In production always set DASHBOARD_API_KEY to a strong random string.
    """
    settings = get_settings()
    expected = settings.dashboard_api_key
    if not expected:
        return  # dev mode — no key configured, allow all
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
