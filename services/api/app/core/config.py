from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "geo-track-api"
    database_url: str = "postgresql+asyncpg://geo:geo@localhost:5432/geo_track"
    database_schema: str = ""
    rabbitmq_url: str = "amqp://geo:geo@localhost:5672/"
    rabbitmq_stream_port: int = 5552
    redis_url: str = "redis://localhost:6379/0"
    session_secret: str = "dev-session-secret"
    internal_token: str = "dev-internal-token"
    log_level: str = "INFO"
    throughput_plug: bool = True
    telemetry_partition_interval_seconds: int = 3600
    telemetry_batch_window_seconds: float = 0.1
    telemetry_batch_max_size: int = 1_000
    telemetry_prefetch: int = 10_000
    pool_size: int = 5
    pool_overflow: int = 2


settings = Settings()
