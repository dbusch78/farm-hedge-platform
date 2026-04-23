"""Central configuration via pydantic-settings. Import `settings` everywhere."""

from datetime import date
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore")

    user: str = "farm"
    password: str = "changeme"
    db: str = "farm_platform"
    dsn: str = "postgresql://farm:changeme@timescaledb:5432/farm_platform"


class MongoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MONGO_", extra="ignore")

    uri: str = "mongodb://farm:changeme@mongodb:27017/farm_platform?authSource=admin"


class AnthropicSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", extra="ignore")

    api_key: str = ""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1000


class AmbientSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AMBIENT_", extra="ignore")

    api_key: str = ""
    app_key: str = ""


class AlpacaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALPACA_", extra="ignore")

    paper_api_key: str = ""
    paper_secret_key: str = ""
    paper_base_url: str = "https://paper-api.alpaca.markets"
    live_api_key: str = ""
    live_secret_key: str = ""
    live_base_url: str = "https://api.alpaca.markets"


class NewsSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    newsapi_key: str = ""
    finnhub_key: str = ""
    quiver_api_key: str = ""


class FarmSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    planting_date_corn: date = date(2025, 5, 1)
    planting_date_beans: date = date(2025, 5, 10)
    expected_bushels_corn: int = 45_000
    expected_bushels_beans: int = 18_000


class ScheduleSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    futures_feed_interval_min: int = Field(default=15, alias="FUTURES_FEED_INTERVAL_MIN")
    weather_feed_interval_hrs: int = Field(default=6, alias="WEATHER_FEED_INTERVAL_HRS")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    mongo: MongoSettings = Field(default_factory=MongoSettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    ambient: AmbientSettings = Field(default_factory=AmbientSettings)
    alpaca: AlpacaSettings = Field(default_factory=AlpacaSettings)
    news: NewsSettings = Field(default_factory=NewsSettings)
    farm: FarmSettings = Field(default_factory=FarmSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)


settings = Settings()
