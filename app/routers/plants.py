from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_api_key
from app.epias_service import fetch_power_plants, fetch_prices_and_generation
from app.eptr_client import get_eptr
from app.schemas import PlantSeriesResponse, PowerPlantsResponse

router = APIRouter(tags=["power-plants"])

_TR = ZoneInfo("Europe/Istanbul")


def _today_istanbul() -> date:
    return datetime.now(_TR).date()


def _parse_ymd(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid date {s!r}: {e}") from e


def _validate_range(start: date, end: date) -> None:
    if start > end:
        raise HTTPException(
            status_code=422, detail="start_date must be on or before end_date"
        )
    today = _today_istanbul()
    if end >= today:
        raise HTTPException(
            status_code=400,
            detail=f"end_date must be strictly before today ({today.isoformat()} Europe/Istanbul)",
        )


@router.get("/power-plants", response_model=PowerPlantsResponse)
def list_power_plants(
    _: None = Depends(verify_api_key),
    eptr=Depends(get_eptr),
) -> PowerPlantsResponse:
    try:
        plants = fetch_power_plants(eptr)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"EPİAŞ upstream error: {e!s}") from e
    return PowerPlantsResponse(plants=plants)


@router.get(
    "/power-plants/{pp_id}/prices-and-generation",
    response_model=PlantSeriesResponse,
)
def plant_prices_and_generation(
    pp_id: int,
    start_date: str = Query(..., description="YYYY-MM-DD inclusive"),
    end_date: str = Query(..., description="YYYY-MM-DD inclusive"),
    _: None = Depends(verify_api_key),
    eptr=Depends(get_eptr),
) -> PlantSeriesResponse:
    start = _parse_ymd(start_date)
    end = _parse_ymd(end_date)
    _validate_range(start, end)
    try:
        payload = fetch_prices_and_generation(eptr, pp_id, start, end)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"EPİAŞ upstream error: {e!s}") from e
    return PlantSeriesResponse.model_validate(payload)
