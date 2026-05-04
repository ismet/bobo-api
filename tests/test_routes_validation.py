"""Route validation (dates, Istanbul today rule) with mocked eptr."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.eptr_client import get_eptr
from app.main import app


def _istanbul_today() -> str:
    return datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()


def test_invalid_date_query_returns_422():
    app.dependency_overrides[get_eptr] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/power-plants/1/prices-and-generation",
                params={"start_date": "not-a-date", "end_date": "2025-01-02"},
            )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_start_after_end_returns_422():
    app.dependency_overrides[get_eptr] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/power-plants/1/prices-and-generation",
                params={"start_date": "2025-02-01", "end_date": "2025-01-01"},
            )
        assert r.status_code == 422
        assert "before" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_end_date_not_before_today_returns_400():
    app.dependency_overrides[get_eptr] = lambda: MagicMock()
    today = _istanbul_today()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/power-plants/1/prices-and-generation",
                params={"start_date": "2020-01-01", "end_date": today},
            )
        assert r.status_code == 400
        assert today in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_yesterday_range_returns_200_mocked():
    YESTERDAY = (datetime.now(ZoneInfo("Europe/Istanbul")).date() - timedelta(days=1)).isoformat()

    class Mini:
        def call(self, key: str, **kwargs):
            import pandas as pd

            if key == "mcp":
                d = kwargs["start_date"]
                return pd.DataFrame([{"date": d, "hour": 0, "mcp": 1.0}])
            if key == "rt-gen":
                d = kwargs["start_date"]
                return pd.DataFrame([{"date": d, "hour": 0, "total": 2.0}])
            raise AssertionError(key)

    app.dependency_overrides[get_eptr] = lambda: Mini()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/power-plants/9/prices-and-generation",
                params={"start_date": YESTERDAY, "end_date": YESTERDAY},
            )
        assert r.status_code == 200
    finally:
        app.dependency_overrides.clear()
