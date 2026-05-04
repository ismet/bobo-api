from datetime import date

import pandas as pd

from app.epias_service import fetch_mcp_prices, fetch_prices_and_generation
from app.chunking import iter_date_chunks


def test_iter_date_chunks_single_day():
    chunks = list(iter_date_chunks(date(2025, 1, 1), date(2025, 1, 1), max_days=89))
    assert chunks == [(date(2025, 1, 1), date(2025, 1, 1))]


def test_iter_date_chunks_exact_span():
    chunks = list(iter_date_chunks(date(2025, 1, 1), date(2025, 3, 30), max_days=89))
    assert len(chunks) == 1
    assert chunks[0] == (date(2025, 1, 1), date(2025, 3, 30))


def test_iter_date_chunks_splits_at_89_days():
    # 89 days inclusive: Jan 1 .. Mar 30 = ? 
    # Jan has 31, Feb 28/29, Mar 31 -> 31+28+30 = 89 from Jan1? Jan1 + 88 days = Mar 29? 
    # Let's use 90 days range to force 2 chunks
    start = date(2025, 1, 1)
    end = date(2025, 4, 1)  # > 89 days from Jan 1
    chunks = list(iter_date_chunks(start, end, max_days=89))
    assert len(chunks) >= 2
    # contiguous: first chunk end + 1 day == second chunk start
    for i in range(len(chunks) - 1):
        a_end = chunks[i][1]
        b_start = chunks[i + 1][0]
        assert (b_start - a_end).days == 1
    assert chunks[0][0] == start
    assert chunks[-1][1] == end


def test_iter_date_chunks_invalid():
    import pytest

    with pytest.raises(ValueError):
        list(iter_date_chunks(date(2025, 2, 1), date(2025, 1, 1)))
    with pytest.raises(ValueError):
        list(iter_date_chunks(date(2025, 1, 1), date(2025, 1, 2), max_days=0))


class _FakeEptr:
    def __init__(self):
        self.mcp_calls: list[tuple[str, str]] = []
        self.rt_calls: list[tuple[str, str, int]] = []

    def call(self, key: str, **kwargs):
        if key == "mcp":
            s, e = kwargs["start_date"], kwargs["end_date"]
            self.mcp_calls.append((s, e))
            return pd.DataFrame(
                [
                    {"date": s, "hour": 0, "mcp": 100.0},
                ]
            )
        if key == "rt-gen":
            s, e = kwargs["start_date"], kwargs["end_date"]
            self.rt_calls.append((s, e, kwargs["pp_id"]))
            return pd.DataFrame(
                [
                    {"date": s, "hour": 0, "total": 1.0},
                ]
            )
        raise AssertionError(key)


def test_fetch_mcp_prices_merges_chunks():
    fake = _FakeEptr()
    out = fetch_mcp_prices(fake, date(2025, 1, 1), date(2025, 3, 15))
    assert len(fake.mcp_calls) >= 2  # 31-day chunks cover > 31 days
    assert any(row["priceEur"] == 100.0 for row in out)


def test_fetch_prices_and_generation_calls_rt_gen_chunked():
    fake = _FakeEptr()
    res = fetch_prices_and_generation(fake, 2800, date(2025, 1, 1), date(2025, 4, 1))
    assert res["plant_id"] == 2800
    assert len(fake.rt_calls) >= 2
    assert len(res["prices"]) == len(res["powers"])
    assert res["num_items"] == len(res["prices"])
    assert res["num_total_hours"] == res["num_items"] + res["num_missing_hours"]
