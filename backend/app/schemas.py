from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class WeatherOverride(BaseModel):
    avg_temp_c: float | None = Field(default=None, ge=0, le=55)
    rainfall_mm: float | None = Field(default=None, ge=0, le=1000)
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: str
    ward_id: str
    horizon_weeks: Literal[2, 4]
    as_of_date: date | None = None
    weather_override: WeatherOverride | None = None


class PredictionResponse(BaseModel):
    city: str
    ward_id: str
    horizon_weeks: int
    reference_date: str
    forecast_target_date: str
    predicted_cases: float
    risk_level: str
    risk_thresholds: dict
    weather_inputs: dict
    risk_drivers: list[dict]
    model_name: str
    data_note: str
    prediction_id: str | None = None
