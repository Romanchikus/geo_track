from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeviceMode(StrEnum):
    all = "all"
    percent = "percent"
    ids = "ids"


class SubscriptionCreate(BaseModel):
    coordinates: list[list[float]] = Field(min_length=3, max_length=512)
    mode: DeviceMode
    percent: int | None = Field(default=None, ge=1, le=100)
    device_ids: list[int] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def check_selection(self) -> "SubscriptionCreate":
        if self.mode is DeviceMode.percent and self.percent is None:
            raise ValueError("percent is required when mode is percent")
        if self.mode is DeviceMode.ids and not self.device_ids:
            raise ValueError("device_ids is required when mode is ids")
        return self


class SubscriptionUpdate(BaseModel):
    coordinates: list[list[float]] | None = Field(default=None, min_length=3, max_length=512)
    mode: DeviceMode | None = None
    percent: int | None = Field(default=None, ge=1, le=100)
    device_ids: list[int] | None = Field(default=None, max_length=10_000)

    @model_validator(mode="after")
    def check_change(self) -> "SubscriptionUpdate":
        if self.coordinates is None and self.mode is None and self.device_ids is None:
            raise ValueError("coordinates or device_ids is required")
        if self.mode is DeviceMode.percent and self.percent is None:
            raise ValueError("percent is required when mode is percent")
        replacing_ids = self.mode is DeviceMode.ids or (self.mode is None and self.device_ids is not None)
        if replacing_ids and not self.device_ids:
            raise ValueError("device_ids must not be empty")
        return self


class SubscriptionDevice(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_id: int
    device_id: int


class SubscriptionArea(BaseModel):
    polygon_id: int
    coordinates: list[list[float]]
    devices: list[SubscriptionDevice]
