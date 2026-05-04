"""Edge cases for date parsing, chunking, merged fetches, and route range rules."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from app.chunking import iter_date_chunks
from app.epias_service import (
    _MCP_CHUNK_DAYS,
    _RT_GEN_CHUNK_DAYS,
    _concat_unique,
    _normalize_date_cell,
    _norm_hour,
    dataframe_to_mcp_prices,
    fetch_mcp_prices,
    fetch_prices_and_generation,
    fetch_rt_gen_chunked,
)
from app.eptr_client import get_eptr
from app.main import app


class TestNormalizeDateCell:
    def test_iso_datetime_z(self):
        assert _normalize_date_cell("2026-05-03T21:30:00Z") == "2026-05-03"

    def test_iso_with_offset(self):
        assert _normalize_date_cell("2026-05-03T00:00:00+03:00") == "2026-05-03"

    def test_plain_date_string(self):
        assert _normalize_date_cell(" 2025-12-31 ") == "2025-12-31"

    def test_short_string_no_crash(self):
        assert _normalize_date_cell("2025-1-1") == "2025-1-1"

    def test_pandas_timestamp(self):
        ts = pd.Timestamp("2026-05-03 14:00:00+03:00")
        assert _normalize_date_cell(ts) == "2026-05-03"

    def test_python_datetime(self):
        dt = datetime(2026, 1, 2, 15, 30)
        assert _normalize_date_cell(dt) == "2026-01-02"

    def test_none_returns_empty(self):
        assert _normalize_date_cell(None) == ""

    def test_nan_returns_empty(self):
        assert _normalize_date_cell(float("nan")) == ""


class TestNormHour:
    def test_int(self):
        assert _norm_hour(0) == 0
        assert _norm_hour(23) == 23

    def test_hh_mm(self):
        assert _norm_hour("00:00") == 0
        assert _norm_hour(" 23:59 ") == 23

    def test_string_int(self):
        assert _norm_hour("5") == 5

    def test_invalid_str(self):
        assert _norm_hour("noon") is None

    def test_numpy_hour_integer_like(self):
        import numpy as np

        assert _norm_hour(np.int64(12)) == 12


class TestIterDateChunks:
    def test_single_day_max_31(self):
        chunks = list(
            iter_date_chunks(date(2025, 6, 10), date(2025, 6, 10), max_days=31)
        )
        assert chunks == [(date(2025, 6, 10), date(2025, 6, 10))]

    def test_exactly_31_days_inclusive_one_chunk(self):
        start, end = date(2025, 1, 1), date(2025, 1, 31)
        chunks = list(iter_date_chunks(start, end, max_days=31))
        assert len(chunks) == 1
        assert chunks[0] == (start, end)

    def test_32_days_splits_into_two_chunks_max_31(self):
        chunks = list(
            iter_date_chunks(date(2025, 1, 1), date(2025, 2, 1), max_days=31)
        )
        assert len(chunks) == 2
        assert chunks[0] == (date(2025, 1, 1), date(2025, 1, 31))
        assert chunks[1] == (date(2025, 2, 1), date(2025, 2, 1))

    def test_leap_year_feb_29_included(self):
        chunks = list(
            iter_date_chunks(date(2024, 2, 28), date(2024, 3, 1), max_days=31)
        )
        assert chunks == [(date(2024, 2, 28), date(2024, 3, 1))]

    def test_year_boundary(self):
        chunks = list(
            iter_date_chunks(date(2025, 12, 30), date(2026, 1, 2), max_days=31)
        )
        assert chunks[0][0] == date(2025, 12, 30)
        assert chunks[-1][1] == date(2026, 1, 2)
        # contiguous coverage
        for i in range(len(chunks) - 1):
            assert (chunks[i + 1][0] - chunks[i][1]).days == 1

    def test_max_days_one_each_calendar_day(self):
        chunks = list(iter_date_chunks(date(2025, 3, 1), date(2025, 3, 3), max_days=1))
        assert chunks == [
            (date(2025, 3, 1), date(2025, 3, 1)),
            (date(2025, 3, 2), date(2025, 3, 2)),
            (date(2025, 3, 3), date(2025, 3, 3)),
        ]

    def test_89_day_window_exact_single_chunk(self):
        start = date(2025, 1, 1)
        end = start + timedelta(days=88)
        chunks = list(iter_date_chunks(start, end, max_days=89))
        assert len(chunks) == 1
        assert chunks[0] == (start, end)


class TestConcatUnique:
    def test_dedupes_same_date_hour_keeps_last(self):
        df1 = pd.DataFrame(
            [{"date": "2025-01-01", "hour": 0, "mcp": 1.0}]
        )
        df2 = pd.DataFrame(
            [{"date": "2025-01-01", "hour": 0, "mcp": 9.9}]
        )
        merged = _concat_unique([df1, df2], ["date", "hour"])
        assert len(merged) == 1
        assert float(merged.iloc[0]["mcp"]) == 9.9

    def test_sorts_by_date_hour(self):
        df = pd.DataFrame(
            [
                {"date": "2025-01-02", "hour": 1, "mcp": 2.0},
                {"date": "2025-01-01", "hour": 5, "mcp": 1.0},
            ]
        )
        merged = _concat_unique([df], ["date", "hour"])
        assert list(merged["date"]) == ["2025-01-01", "2025-01-02"]


class RecordingEptrMcp:
    """Records MCP calls with ISO date strings."""

    def __init__(self):
        self.mcp_calls: list[tuple[str, str]] = []

    def call(self, key: str, **kwargs):
        if key != "mcp":
            raise AssertionError(key)
        self.mcp_calls.append((kwargs["start_date"], kwargs["end_date"]))
        d = kwargs["start_date"]
        return pd.DataFrame([{"date": d, "hour": 0, "priceEur": 1.0}])


def test_fetch_mcp_prices_issues_iso_dates_per_chunk():
    e = RecordingEptrMcp()
    start, end = date(2025, 1, 1), date(2025, 2, 15)
    fetch_mcp_prices(e, start, end)
    assert e.mcp_calls[0][0] == "2025-01-01"
    # first window ends Jan 31 (31-day inclusive)
    assert e.mcp_calls[0][1] == "2025-01-31"
    assert e.mcp_calls[1][0] == "2025-02-01"
    assert e.mcp_calls[-1][1] == "2025-02-15"
    # no gaps: each chunk start == previous end + 1 day
    for i in range(1, len(e.mcp_calls)):
        prev_end = date.fromisoformat(e.mcp_calls[i - 1][1])
        cur_start = date.fromisoformat(e.mcp_calls[i][0])
        assert cur_start - prev_end == timedelta(days=1)


def test_fetch_mcp_single_day_single_request():
    class One:
        def __init__(self):
            self.n = 0

        def call(self, key, **kwargs):
            self.n += 1
            assert kwargs["start_date"] == kwargs["end_date"] == "2025-06-15"
            return pd.DataFrame(
                [{"date": "2025-06-15", "hour": 12, "mcp": 50.0}]
            )

    o = One()
    out = fetch_mcp_prices(o, date(2025, 6, 15), date(2025, 6, 15))
    assert o.n == 1
    assert out == [{"date": "2025-06-15", "hour": 12, "priceEur": 50.0}]


class RecordingEptrRtGen:
    def __init__(self):
        self.rt_calls: list[tuple[str, str, int]] = []

    def call(self, key: str, **kwargs):
        if key != "rt-gen":
            raise AssertionError(key)
        self.rt_calls.append(
            (kwargs["start_date"], kwargs["end_date"], kwargs["pp_id"])
        )
        d = kwargs["start_date"]
        return pd.DataFrame([{"date": d, "hour": 0, "total": 1.0}])


def test_fetch_rt_gen_respects_89_day_windows():
    e = RecordingEptrRtGen()
    start, end = date(2025, 1, 1), date(2025, 6, 1)
    fetch_rt_gen_chunked(e, start, end, pp_id=99)
    assert len(e.rt_calls) >= 2
    for _s, _e, pid in e.rt_calls:
        assert pid == 99
        cs, ce = date.fromisoformat(_s), date.fromisoformat(_e)
        assert (ce - cs).days + 1 <= _RT_GEN_CHUNK_DAYS
    # contiguous
    for i in range(1, len(e.rt_calls)):
        prev = date.fromisoformat(e.rt_calls[i - 1][1])
        nxt = date.fromisoformat(e.rt_calls[i][0])
        assert nxt - prev == timedelta(days=1)


def test_fetch_prices_and_generation_passes_same_calendar_range_to_both():
    class Both:
        def __init__(self):
            self.mcp_ranges: list[tuple[str, str]] = []
            self.rt_ranges: list[tuple[str, str]] = []

        def call(self, key: str, **kwargs):
            if key == "mcp":
                self.mcp_ranges.append(
                    (kwargs["start_date"], kwargs["end_date"])
                )
                return pd.DataFrame()
            if key == "rt-gen":
                self.rt_ranges.append(
                    (kwargs["start_date"], kwargs["end_date"])
                )
                return pd.DataFrame()
            raise AssertionError(key)

    b = Both()
    s, e = date(2025, 4, 1), date(2025, 4, 5)
    fetch_prices_and_generation(b, 1, s, e)
    assert b.mcp_ranges[0][0] == b.rt_ranges[0][0] == "2025-04-01"
    assert b.mcp_ranges[-1][1] == b.rt_ranges[-1][1] == "2025-04-05"


def test_mcp_chunk_count_matches_constant():
    """Span 70 days -> ceil(70/31) = 3 windows with max_days=31."""
    e = RecordingEptrMcp()
    start, end = date(2025, 1, 1), date(2025, 3, 11)  # Jan1..Mar11 = 70 days
    fetch_mcp_prices(e, start, end)
    expected = (70 + _MCP_CHUNK_DAYS - 1) // _MCP_CHUNK_DAYS
    assert len(e.mcp_calls) == expected


def test_empty_upstream_frames_yield_empty_lists():
    class Empty:
        def call(self, key, **kwargs):
            return pd.DataFrame()

    e = Empty()
    assert fetch_mcp_prices(e, date(2025, 1, 1), date(2025, 1, 3)) == []
    assert fetch_rt_gen_chunked(e, date(2025, 1, 1), date(2025, 1, 3), 1) == []


def test_duplicate_hours_after_concat_normalized_once():
    """Same hour key from two chunks -> one row in API output."""
    df1 = pd.DataFrame(
        [{"date": "2025-01-31", "hour": 23, "priceEur": 1.0}]
    )
    df2 = pd.DataFrame(
        [{"date": "2025-01-31", "hour": 23, "priceEur": 2.0}]
    )
    merged = _concat_unique([df1, df2], ["date", "hour"])
    rows = dataframe_to_mcp_prices(merged)
    assert len(rows) == 1
    assert rows[0]["priceEur"] == 2.0


@patch("app.routers.plants._today_istanbul", return_value=date(2026, 6, 15))
def test_route_end_must_be_before_mocked_today(_mock_today):
    app.dependency_overrides[get_eptr] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            ok = client.get(
                "/power-plants/1/prices-and-generation",
                params={"start_date": "2026-06-10", "end_date": "2026-06-14"},
            )
            bad = client.get(
                "/power-plants/1/prices-and-generation",
                params={"start_date": "2026-06-10", "end_date": "2026-06-15"},
            )
    finally:
        app.dependency_overrides.clear()
    assert ok.status_code == 200
    assert bad.status_code == 400
    assert "2026-06-15" in bad.json()["detail"]


@patch("app.routers.plants._today_istanbul", return_value=date(2026, 6, 15))
def test_route_same_start_end_allowed_before_today(_mock_today):
    class Mini:
        def call(self, key, **kwargs):
            import pandas as pd

            d = kwargs["start_date"]
            if key == "mcp":
                return pd.DataFrame(
                    [{"date": d, "hour": 0, "priceEur": 1.0}]
                )
            if key == "rt-gen":
                return pd.DataFrame(
                    [{"date": d, "hour": 0, "total": 0.0}]
                )
            raise AssertionError(key)

    app.dependency_overrides[get_eptr] = lambda: Mini()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/power-plants/7/prices-and-generation",
                params={"start_date": "2026-06-14", "end_date": "2026-06-14"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["start_date"] == "2026-06-14 00:00:00"
    assert body["end_date"] == "2026-06-14 23:00:00"
    assert body["num_total_hours"] == 24
    assert body["num_items"] == 1
    assert body["num_missing_hours"] == 23
    assert body["prices"] == [1.0]
    assert body["powers"] == [0.0]
