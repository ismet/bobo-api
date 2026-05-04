"""
Live EPİAŞ tests (real eptr2 + credentials).
Requires `.env` with EPTR_USERNAME / EPTR_PASSWORD.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.eptr_client import reset_eptr_client
from app.main import app
from tests.conftest import credentials_configured


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not credentials_configured(),
        reason="EPTR_USERNAME / EPTR_PASSWORD missing (configure .env)",
    ),
]


@pytest.fixture(autouse=True)
def _reset_eptr_singleton():
    reset_eptr_client()
    yield
    reset_eptr_client()


def test_live_list_power_plants():
    with TestClient(app) as client:
        r = client.get("/power-plants")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "plants" in data
    assert len(data["plants"]) >= 1
    p0 = data["plants"][0]
    for key in ("id", "name", "eic", "shortName"):
        assert key in p0


def test_live_prices_and_generation_single_plant():
    tr = ZoneInfo("Europe/Istanbul")
    today = datetime.now(tr).date()
    end = today - timedelta(days=1)
    start = end - timedelta(days=2)
    if start > end:
        pytest.skip("date range collapse")

    with TestClient(app) as client:
        pr = client.get("/power-plants")
        assert pr.status_code == 200
        plants = pr.json()["plants"]
        raw_id = plants[0]["id"]
        pp_id = int(raw_id) if not isinstance(raw_id, int) else raw_id

        r = client.get(
            f"/power-plants/{pp_id}/prices-and-generation",
            params={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plant_id"] == pp_id
    assert body["start_date"] == f"{start.isoformat()} 00:00:00"
    assert body["end_date"] == f"{end.isoformat()} 23:00:00"
    assert isinstance(body["prices"], list)
    assert isinstance(body["powers"], list)
    assert len(body["prices"]) == len(body["powers"])
    assert body["num_items"] == len(body["prices"])
    if body["prices"]:
        assert isinstance(body["prices"][0], (int, float))
    if body["powers"]:
        assert isinstance(body["powers"][0], (int, float))


def test_live_health():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
