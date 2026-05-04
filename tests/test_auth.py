"""API key guard when API_KEY is set."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.eptr_client import get_eptr
from app.main import app


def test_protected_routes_401_without_key_when_api_key_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "supersecret")
    app.dependency_overrides[get_eptr] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            r_plants = client.get("/power-plants")
            r_series = client.get(
                "/power-plants/1/prices-and-generation",
                params={"start_date": "2020-01-01", "end_date": "2020-01-02"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r_plants.status_code == 401
    assert r_series.status_code == 401


def test_protected_routes_200_with_correct_header(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "supersecret")

    class Mini:
        def call(self, key: str, **kwargs):
            import pandas as pd

            if key == "pp-list":
                return pd.DataFrame(
                    [{"id": 1, "name": "P", "eic": "e", "shortName": "s"}]
                )
            raise AssertionError(key)

    app.dependency_overrides[get_eptr] = lambda: Mini()
    try:
        with TestClient(app) as client:
            r = client.get("/power-plants", headers={"X-API-Key": "supersecret"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["plants"][0]["id"] == 1


def test_wrong_api_key_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "correct")
    app.dependency_overrides[get_eptr] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            r = client.get("/power-plants", headers={"X-API-Key": "wrong"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 401


def test_health_never_requires_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "required-for-other-routes")
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
