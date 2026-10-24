from pydantic import BaseModel


class Statistics(BaseModel):
    devices: int
    telemetry: int
    telemetry_last_day: int
    subscriptions: int
    users: int
