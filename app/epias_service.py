from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

_ISTANBUL = ZoneInfo("Europe/Istanbul")

import pandas as pd

from app.chunking import iter_date_chunks

# MCP: chunk defensively; upstream often tolerates months but varies by environment.
_MCP_CHUNK_DAYS = 31
_RT_GEN_CHUNK_DAYS = 89


def _normalize_date_cell(val: Any) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if "T" in s:
        return s.split("T", 1)[0][:10]
    return s[:10] if len(s) >= 10 else s


def _coerce_plant_id(val: Any) -> int | str | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float) and val == int(val):
        return int(val)
    s = str(val).strip()
    if s.isdigit():
        return int(s)
    return s


def _norm_hour(val: Any) -> int | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    if isinstance(val, str):
        s = val.strip()
        if ":" in s:
            parts = s.split(":", 1)
            try:
                return int(parts[0])
            except ValueError:
                return None
        try:
            return int(s)
        except ValueError:
            return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _lower_key_map(rec: dict) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in rec.items()}


def _pick_ci(norm_lower: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        kk = k.lower()
        if kk in norm_lower:
            return norm_lower[kk]
    return None


def dataframe_to_power_plants(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out: list[dict[str, Any]] = []
    for raw in df.to_dict(orient="records"):
        low = _lower_key_map(raw)
        pid = _pick_ci(low, "id", "powerplantid", "power_plant_id")
        name = _pick_ci(low, "name", "powerplantname", "plantname")
        eic = _pick_ci(low, "eic")
        short = _pick_ci(low, "shortname", "short_name", "abbreviation")
        if pid is None and name is None:
            continue
        cid = _coerce_plant_id(pid)
        if cid is None:
            continue
        out.append(
            {
                "id": cid,
                "name": str(name) if name is not None else "",
                "eic": "" if eic is None else str(eic),
                "shortName": "" if short is None else str(short),
            }
        )
    return out


def _find_date_hour_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    date_c = None
    hour_c = None
    for c in df.columns:
        cl = str(c).lower()
        if cl == "date" and date_c is None:
            date_c = c
        elif cl == "hour" and hour_c is None:
            hour_c = c
    if date_c is None:
        for c in df.columns:
            if "date" in str(c).lower():
                date_c = c
                break
    if hour_c is None:
        for c in df.columns:
            if str(c).lower() == "time" or str(c).lower() == "hour":
                hour_c = c
                break
    return date_c, hour_c


def _find_mcp_price_column(df: pd.DataFrame) -> str | None:
    priority = [
        "priceeur",
        "price_eur",
        "ptf",
        "mcp",
        "price",
        "marketclearingprice",
        "market_clearing_price",
    ]
    cols_lower = {str(c).lower(): c for c in df.columns}
    for p in priority:
        if p in cols_lower:
            return cols_lower[p]
    return None


def dataframe_to_mcp_prices(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows: date, hour, priceEur (value from MCP column; may be TL/MWh)."""
    if df.empty:
        return []
    date_c, hour_c = _find_date_hour_columns(df)
    price_c = _find_mcp_price_column(df)
    if not date_c or not hour_c or not price_c:
        return []
    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        d = _normalize_date_cell(row[date_c])
        h = _norm_hour(row[hour_c])
        if not d or h is None:
            continue
        v = row[price_c]
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            try:
                price = float(v)
            except (TypeError, ValueError):
                continue
        else:
            continue
        out.append({"date": d, "hour": h, "priceEur": price})
    return out


def _find_total_column(df: pd.DataFrame, date_col: str, hour_col: str | None) -> str | None:
    skip = {date_col}
    if hour_col:
        skip.add(hour_col)
    for c in df.columns:
        if c in skip:
            continue
        cl = str(c).lower()
        if cl in ("hour", "date"):
            continue
        if cl in ("total", "generation", "value", "mwh", "quantity"):
            return c
    for c in df.columns:
        if c in skip:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None


def dataframe_to_generation(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    date_c, hour_c = _find_date_hour_columns(df)
    if not date_c:
        return []
    total_c = _find_total_column(df, date_c, hour_c)
    if not total_c:
        return []
    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        d = _normalize_date_cell(row[date_c])
        h = _norm_hour(row[hour_c]) if hour_c else 0
        if not d:
            continue
        if h is None:
            h = 0
        v = row[total_c]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        try:
            total = float(v)
        except (TypeError, ValueError):
            continue
        out.append({"date": d, "hour": h, "total": total})
    return out


def _concat_unique(dfs: list[pd.DataFrame], sort_keys: list[str]) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame()
    merged = pd.concat(dfs, ignore_index=True)
    if merged.empty:
        return merged
    avail = [k for k in sort_keys if k in merged.columns]
    if avail:
        merged = merged.drop_duplicates(subset=avail, keep="last")
        merged = merged.sort_values(by=avail)
    return merged


def fetch_power_plants(eptr: Any) -> list[dict[str, Any]]:
    df: pd.DataFrame = eptr.call("pp-list")
    return dataframe_to_power_plants(df)


def fetch_mcp_prices(eptr: Any, start: date, end: date) -> list[dict[str, Any]]:
    dfs: list[pd.DataFrame] = []
    for cs, ce in iter_date_chunks(start, end, max_days=_MCP_CHUNK_DAYS):
        df = eptr.call(
            "mcp",
            start_date=cs.isoformat(),
            end_date=ce.isoformat(),
        )
        if isinstance(df, pd.DataFrame) and not df.empty:
            dfs.append(df)
    combined = _concat_unique(dfs, ["date", "hour"])
    return dataframe_to_mcp_prices(combined)


def _istanbul_hour_label(day: date, hour: int) -> str:
    dt = datetime(day.year, day.month, day.day, hour, 0, 0, tzinfo=_ISTANBUL)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _row_hour(val: Any) -> int | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, str):
        return _norm_hour(val)
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return _norm_hour(val)


def _merged_float_map(rows: list[dict[str, Any]], value_key: str) -> dict[tuple[str, int], float]:
    out: dict[tuple[str, int], float] = {}
    for r in rows:
        dk = _normalize_date_cell(r.get("date"))
        h = _row_hour(r.get("hour"))
        if not dk or h is None:
            continue
        v = r.get(value_key)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        out[(dk, h)] = fv
    return out


def align_prices_and_powers_rows(
    start: date, end: date, pp_id: int, price_rows: list[dict[str, Any]], gen_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    pm = _merged_float_map(price_rows, "priceEur")
    gm = _merged_float_map(gen_rows, "total")
    prices_out: list[float] = []
    powers_out: list[float] = []
    missing_price: list[str] = []
    missing_power: list[str] = []

    total_slots = ((end - start).days + 1) * 24
    num_missing_hours = 0
    delta = timedelta(days=1)
    d = start
    while d <= end:
        dkey = _normalize_date_cell(d.isoformat())
        for hour in range(24):
            ts = _istanbul_hour_label(d, hour)
            has_p = (dkey, hour) in pm
            has_g = (dkey, hour) in gm
            if has_p and has_g:
                prices_out.append(pm[(dkey, hour)])
                powers_out.append(gm[(dkey, hour)])
                continue
            num_missing_hours += 1
            if not has_p:
                missing_price.append(ts)
            if not has_g:
                missing_power.append(ts)
        d += delta

    num_items = total_slots - num_missing_hours
    return {
        "plant_id": pp_id,
        "start_date": _istanbul_hour_label(start, 0),
        "end_date": _istanbul_hour_label(end, 23),
        "num_items": num_items,
        "num_total_hours": total_slots,
        "num_missing_hours": num_missing_hours,
        "prices": prices_out,
        "powers": powers_out,
        "missing_price_dates": missing_price,
        "missing_power_dates": missing_power,
    }


def fetch_rt_gen_chunked(eptr: Any, start: date, end: date, pp_id: int) -> list[dict[str, Any]]:
    dfs: list[pd.DataFrame] = []
    for cs, ce in iter_date_chunks(start, end, max_days=_RT_GEN_CHUNK_DAYS):
        df = eptr.call(
            "rt-gen",
            start_date=cs.isoformat(),
            end_date=ce.isoformat(),
            pp_id=pp_id,
        )
        if isinstance(df, pd.DataFrame) and not df.empty:
            dfs.append(df)
    combined = _concat_unique(dfs, ["date", "hour"])
    return dataframe_to_generation(combined)


def fetch_prices_and_generation(
    eptr: Any, pp_id: int, start: date, end: date
) -> dict[str, Any]:
    prices = fetch_mcp_prices(eptr, start, end)
    generation = fetch_rt_gen_chunked(eptr, start, end, pp_id)
    return align_prices_and_powers_rows(start, end, pp_id, prices, generation)
