"""Pytest fixtures and env bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


@pytest.fixture(autouse=True)
def _tests_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """So `.env` may contain API_KEY for local runs without breaking tests."""
    monkeypatch.setenv("API_KEY", "")


def credentials_configured() -> bool:
    u = os.environ.get("EPTR_USERNAME", "").strip()
    p = os.environ.get("EPTR_PASSWORD", "").strip()
    return bool(u and p)
