from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_settings() -> Settings:
    return Settings()


def verify_api_key(
    x_api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Require ``X-API-Key`` matching ``API_KEY`` when that env var is set (non-empty)."""
    expected = (settings.api_key or "").strip()
    if not expected:
        return
    if (x_api_key or "").strip() != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )
