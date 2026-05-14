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
    # MAC of the outdoor farm station (ignore other devices/channels in account)
    station_mac: str = "C4:5B:BE:5D:33:FE"
    poll_interval_min: int = 5


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


class ElevatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ELEVATOR_", extra="ignore")

    rvc_email: str = ""
    rvc_password: str = ""
    rvc_base: str = "https://shop.rivervalleycoop.com"
    cash_bids_url: str = ""
    futures_url: str = ""  # e.g. https://shop.rivervalleycoop.com/api/v1/commodity/futures
    names: str = ""  # comma-separated elevator names, e.g. "Toulon,Kewanee"
    cookie_path: str = ".cache/elevator_cookies.pkl"
    scraper_interval_hrs: int = 1

    @property
    def elevator_list(self) -> list[str]:
        return [n.strip() for n in self.names.split(",") if n.strip()]


class ScheduleSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    futures_feed_interval_min: int = Field(default=15, alias="FUTURES_FEED_INTERVAL_MIN")
    weather_feed_interval_hrs: int = Field(default=6, alias="WEATHER_FEED_INTERVAL_HRS")
    alert_job_interval_hrs: int = Field(default=24, alias="ALERT_JOB_INTERVAL_HRS")


class AlertSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALERT_", extra="ignore")

    # Phase 1 roll-up: fire when delta drifted AND floor below market AND time left
    zc_roll_threshold: float = 0.15    # futures must be >= this far above strike ($/bu)
    zs_roll_threshold: float = 0.35
    roll_up_min_days: int = 30         # must have at least this many days to expiry
    roll_up_delta_pct: float = 0.50    # current delta < 50% of delta_at_entry
    roll_up_delta_abs: float = 0.15    # OR current delta < this absolute threshold

    # Phase 1 roll-down: fire when deep ITM
    roll_down_zc: float = 0.20         # futures < strike by this much
    roll_down_zs: float = 0.50
    roll_down_delta: float = 0.80      # AND current delta > this

    # Phase 2 take-profit — stage 1 (yellow)
    tp_yellow_days: int = 60           # days to expiry
    tp_yellow_pct: float = 0.70        # current P&L >= 70% of peak

    # Phase 2 take-profit — stage 2 (red)
    tp_red_days: int = 45
    tp_red_pct: float = 0.85           # 85% of peak when <= 60 days left
    tp_retracement: float = 0.20       # position retracted > 20% from peak


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
    elevator: ElevatorSettings = Field(default_factory=ElevatorSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)


settings = Settings()
