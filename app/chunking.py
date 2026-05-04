from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator


def iter_date_chunks(
    start: date, end: date, *, max_days: int = 89
) -> Iterator[tuple[date, date]]:
    """Yield inclusive (chunk_start, chunk_end) windows covering [start, end].

    Each window spans at most ``max_days`` calendar days (inclusive).
    """
    if max_days < 1:
        raise ValueError("max_days must be >= 1")
    if start > end:
        raise ValueError("start must be on or before end")

    span = max_days - 1
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=span), end)
        yield (cur, chunk_end)
        cur = chunk_end + timedelta(days=1)
