-- Farm Platform -- TimescaleDB DDL
-- Run via scripts/init_db.py on first boot.

-- ── Futures prices (ZC, ZS, ZW) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS futures_prices (
    time            TIMESTAMPTZ NOT NULL,
    symbol          VARCHAR(10)  NOT NULL,
    open            NUMERIC(10,4),
    high            NUMERIC(10,4),
    low             NUMERIC(10,4),
    close           NUMERIC(10,4),
    volume          BIGINT,
    source          VARCHAR(20)  DEFAULT 'yfinance',
    stale           BOOLEAN      DEFAULT FALSE
);
SELECT create_hypertable('futures_prices', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_futures_symbol_time ON futures_prices (symbol, time DESC);

-- ── Local cash prices and basis ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cash_prices (
    time            TIMESTAMPTZ NOT NULL,
    elevator        VARCHAR(100) NOT NULL,
    commodity       VARCHAR(20)  NOT NULL,
    cash_price      NUMERIC(8,4) NOT NULL,
    futures_ref     NUMERIC(8,4),
    basis           NUMERIC(8,4),
    contract_month  VARCHAR(10)
);
SELECT create_hypertable('cash_prices', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_cash_elevator_time ON cash_prices (elevator, time DESC);

-- ── Options position P&L snapshots ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS options_snapshots (
    time            TIMESTAMPTZ NOT NULL,
    position_id     VARCHAR(50)  NOT NULL,
    underlying_px   NUMERIC(10,4) NOT NULL,
    option_px       NUMERIC(10,4),
    delta           NUMERIC(6,4),
    premium_paid    NUMERIC(8,4),
    pnl_per_bushel  NUMERIC(8,4),
    net_eff_price   NUMERIC(8,4)
);
SELECT create_hypertable('options_snapshots', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_snapshots_position_time ON options_snapshots (position_id, time DESC);

-- ── On-farm weather station (Ambient Weather) ───────────────────────────────
CREATE TABLE IF NOT EXISTS weather_station_local (
    time                 TIMESTAMPTZ NOT NULL,
    temp_f               NUMERIC(5,2),
    humidity             NUMERIC(5,2),
    rain_hourly          NUMERIC(6,3),
    rain_daily           NUMERIC(6,3),
    wind_speed           NUMERIC(5,2),
    wind_dir             SMALLINT,
    solar_rad            NUMERIC(7,2),
    baro_rel             NUMERIC(7,3),
    soil_temp_1          NUMERIC(5,2),
    wind_gust_mph        NUMERIC(5,2),
    dew_point_f          NUMERIC(5,2),
    uv_index             SMALLINT,
    lightning_day        SMALLINT,
    lightning_distance_mi NUMERIC(5,2)
);
SELECT create_hypertable('weather_station_local', 'time', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_local_time ON weather_station_local (time);
-- Migrations: add new columns to existing installs
ALTER TABLE weather_station_local ADD COLUMN IF NOT EXISTS wind_gust_mph        NUMERIC(5,2);
ALTER TABLE weather_station_local ADD COLUMN IF NOT EXISTS dew_point_f          NUMERIC(5,2);
ALTER TABLE weather_station_local ADD COLUMN IF NOT EXISTS uv_index             SMALLINT;
ALTER TABLE weather_station_local ADD COLUMN IF NOT EXISTS lightning_day        SMALLINT;
ALTER TABLE weather_station_local ADD COLUMN IF NOT EXISTS lightning_distance_mi NUMERIC(5,2);

-- ── Regional weather (Open-Meteo) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weather_regional (
    time            TIMESTAMPTZ NOT NULL,
    region          VARCHAR(50)  NOT NULL,
    temp_c          NUMERIC(5,2),
    precip_mm       NUMERIC(6,2),
    soil_moisture   NUMERIC(5,3),
    et0             NUMERIC(5,2),
    wind_speed_10m  NUMERIC(5,2)
);
SELECT create_hypertable('weather_regional', 'time', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_regional_time_region ON weather_regional (time, region);
CREATE INDEX IF NOT EXISTS idx_weather_regional_region_time ON weather_regional (region, time DESC);

-- ── Planting dates (per crop, per year) ────────────────────────────────────
-- Stores one row per (commodity, year). Used by GDU calculator.
CREATE TABLE IF NOT EXISTS planting_dates (
    commodity       VARCHAR(20)  NOT NULL,
    year            SMALLINT     NOT NULL,
    planted_date    DATE         NOT NULL,
    notes           TEXT,
    PRIMARY KEY (commodity, year)
);

-- ── GDU continuous aggregate ────────────────────────────────────────────────
-- Requires at least one row in weather_station_local before this will materialize.
CREATE MATERIALIZED VIEW IF NOT EXISTS gdu_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)                                             AS day,
    AVG(temp_f)                                                            AS avg_temp_f,
    GREATEST(((MIN(temp_f) + MAX(temp_f)) / 2.0) - 50, 0)                 AS gdu
FROM weather_station_local
GROUP BY day
WITH NO DATA;
