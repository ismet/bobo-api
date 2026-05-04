"""HTTP tests with mocked EPTR2 (no network)."""

from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from app.eptr_client import get_eptr
from app.main import app


class _MockEptrComprehensive:
    """Returns minimal plausible DataFrames for each call key."""

    def call(self, key: str, **kwargs):
        if key == "pp-list":
            return pd.DataFrame(
                [
                    {
                        "id": 42,
                        "name": "Mock Plant",
                        "eic": "12X-ABC--MK",
                        "shortName": "MPL",
                    }
                ]
            )
        if key == "mcp":
            d = kwargs["start_date"]
            return pd.DataFrame(
                [
                    {"date": d, "hour": 10, "mcp": 2500.5},
                    {"date": d, "hour": 11, "mcp": 2600.0},
                ]
            )
        if key == "rt-gen":
            d = kwargs["start_date"]
            return pd.DataFrame(
                [
                    {"date": d, "hour": 10, "total": 15.25},
                    {"date": d, "hour": 11, "total": 14.0},
                ]
            )
        raise AssertionError(f"unexpected call {key!r}")


def test_health_ok():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_power_plants_mocked():
    app.dependency_overrides[get_eptr] = lambda: _MockEptrComprehensive()
    try:
        with TestClient(app) as client:
            r = client.get("/power-plants")
        assert r.status_code == 200
        data = r.json()
        assert "plants" in data
        assert len(data["plants"]) == 1
        p = data["plants"][0]
        assert p["id"] == 42
        assert p["name"] == "Mock Plant"
        assert p["eic"] == "12X-ABC--MK"
        assert p["shortName"] == "MPL"
    finally:
        app.dependency_overrides.clear()


def test_prices_and_generation_mocked():
    app.dependency_overrides[get_eptr] = lambda: _MockEptrComprehensive()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/power-plants/2800/prices-and-generation",
                params={"start_date": "2025-06-01", "end_date": "2025-06-02"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["plant_id"] == 2800
        assert body["start_date"] == "2025-06-01 00:00:00"
        assert body["end_date"] == "2025-06-02 23:00:00"
        assert body["num_total_hours"] == 48
        assert body["num_missing_hours"] == 46
        assert body["num_items"] == 2
        assert body["prices"] == [2500.5, 2600.0]
        assert body["powers"] == [15.25, 14.0]
        assert len(body["missing_price_dates"]) == 46
        assert len(body["missing_power_dates"]) == 46
    finally:
        app.dependency_overrides.clear()


def test_power_plants_upstream_error_becomes_502():
    class Boom:
        def call(self, key: str, **kwargs):
            raise RuntimeError("upstream")

    app.dependency_overrides[get_eptr] = lambda: Boom()
    try:
        with TestClient(app) as client:
            r = client.get("/power-plants")
        assert r.status_code == 502
        assert "upstream" in r.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()
