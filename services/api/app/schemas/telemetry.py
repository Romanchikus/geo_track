from datetime import datetime

from fastapi_filters import FilterField, FilterSet
from pydantic import BaseModel


class TelemetryPoint(BaseModel):
    device_id: int
    latitude: float
    longitude: float
    timestamp: datetime


class TelemetryFilters(FilterSet):
    device_id: FilterField[int]
    timestamp: FilterField[datetime]
