"""Unit tests for DataFrame normalization (no eptr)."""

from __future__ import annotations

import pandas as pd

from app.epias_service import (
    dataframe_to_generation,
    dataframe_to_mcp_prices,
    dataframe_to_power_plants,
)


def test_dataframe_to_power_plants_maps_columns():
    df = pd.DataFrame(
        [
            {
                "powerPlantId": 100,
                "powerPlantName": "Alpha",
                "eic": "E1",
                "shortName": "AL",
            }
        ]
    )
    rows = dataframe_to_power_plants(df)
    assert rows == [
        {"id": 100, "name": "Alpha", "eic": "E1", "shortName": "AL"},
    ]


def test_dataframe_to_mcp_prices_uses_priceEur_key():
    df = pd.DataFrame([{"date": "2025-01-01", "hour": 5, "mcp": 99.5}])
    rows = dataframe_to_mcp_prices(df)
    assert rows == [{"date": "2025-01-01", "hour": 5, "priceEur": 99.5}]


def test_dataframe_to_mcp_prices_eptr_style_hour_and_priceEur_column():
    """Live EPTR2 uses ISO date + 'HH:MM' hour and a priceEur column."""
    df = pd.DataFrame(
        [
            {
                "date": "2026-05-03T00:00:00+03:00",
                "hour": "00:00",
                "price": 174.99,
                "priceEur": 3.33,
            }
        ]
    )
    rows = dataframe_to_mcp_prices(df)
    assert rows == [{"date": "2026-05-03", "hour": 0, "priceEur": 3.33}]


def test_dataframe_to_generation_picks_total_column():
    df = pd.DataFrame([{"date": "2025-01-01", "hour": 3, "total": 12.5}])
    rows = dataframe_to_generation(df)
    assert rows == [{"date": "2025-01-01", "hour": 3, "total": 12.5}]


def test_dataframe_empty():
    assert dataframe_to_power_plants(pd.DataFrame()) == []
    assert dataframe_to_mcp_prices(pd.DataFrame()) == []
    assert dataframe_to_generation(pd.DataFrame()) == []
