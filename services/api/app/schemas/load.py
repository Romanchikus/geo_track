from pydantic import BaseModel, Field, model_validator


class LoadControl(BaseModel):
    speed_kmh: float | None = None
    telemetry_batch_max_size: int | None = None


class LoadUpdate(BaseModel):
    speed_kmh: float | None = Field(default=None, gt=0, le=1_000_000)
    telemetry_batch_max_size: int | None = Field(default=None, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def check_change(self) -> "LoadUpdate":
        if self.speed_kmh is None and self.telemetry_batch_max_size is None:
            raise ValueError("speed_kmh or telemetry_batch_max_size is required")
        return self
