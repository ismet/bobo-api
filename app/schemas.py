from pydantic import BaseModel, Field


class PowerPlant(BaseModel):
    id: int | str
    name: str
    eic: str
    shortName: str


class PowerPlantsResponse(BaseModel):
    plants: list[PowerPlant]


class PlantSeriesResponse(BaseModel):
    plant_id: int
    start_date: str = Field(
        description="First hour of the query range, Europe/Istanbul wall time (YYYY-MM-DD HH:mm:ss)."
    )
    end_date: str = Field(
        description="Last hour **start** in the query range (23:00 on end_date), Europe/Istanbul."
    )
    num_items: int
    num_total_hours: int
    num_missing_hours: int
    prices: list[float] = Field(
        description="MCP values for hours where both price and generation exist; order matches `powers`."
    )
    powers: list[float] = Field(description="Realized generation (MWh) aligned with `prices`.")
    missing_price_dates: list[str] = Field(
        description="Hour starts (YYYY-MM-DD HH:mm:ss, Istanbul) with no MCP price."
    )
    missing_power_dates: list[str] = Field(
        description="Hour starts (YYYY-MM-DD HH:mm:ss, Istanbul) with no generation."
    )
