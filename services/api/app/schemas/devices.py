from pydantic import BaseModel, ConfigDict, Field


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class DeviceBatchCreate(BaseModel):
    count: int = Field(ge=1, le=10_000)


class DeviceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
