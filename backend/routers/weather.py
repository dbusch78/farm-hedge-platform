"""Weather router — local station, regional conditions, GDU, planting dates."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from farm_platform.feeds.gdu_calculator import get_gdu_history, get_gdu_status
from farm_platform.storage.timescale import (
    delete_planting_date,
    get_all_regional_history,
    get_latest_weather_local,
    get_latest_weather_regional,
    get_planting_dates,
    get_rain_totals,
    get_weather_local_history,
    upsert_planting_date,
)

router = APIRouter(prefix="/api/weather", tags=["weather"])

VALID_REGIONS = {"corn_belt", "mato_grosso", "parana", "pampas"}
VALID_CROPS = {"corn", "beans"}


class PlantingDateBody(BaseModel):
    planted_date: date
    notes: str | None = None


def _row_to_dict_local(r) -> dict:
    return {
        "time": r["time"].isoformat(),
        "temp_f": float(r["temp_f"]) if r["temp_f"] is not None else None,
        "humidity": float(r["humidity"]) if r["humidity"] is not None else None,
        "rain_hourly": float(r["rain_hourly"]) if r["rain_hourly"] is not None else None,
        "rain_daily": float(r["rain_daily"]) if r["rain_daily"] is not None else None,
        "wind_speed": float(r["wind_speed"]) if r["wind_speed"] is not None else None,
        "wind_dir": int(r["wind_dir"]) if r["wind_dir"] is not None else None,
        "solar_rad": float(r["solar_rad"]) if r["solar_rad"] is not None else None,
        "baro_rel": float(r["baro_rel"]) if r["baro_rel"] is not None else None,
        "wind_gust_mph": float(r["wind_gust_mph"]) if r["wind_gust_mph"] is not None else None,
        "dew_point_f": float(r["dew_point_f"]) if r["dew_point_f"] is not None else None,
        "uv_index": int(r["uv_index"]) if r["uv_index"] is not None else None,
        "lightning_day": int(r["lightning_day"]) if r["lightning_day"] is not None else None,
        "lightning_distance_mi": float(r["lightning_distance_mi"]) if r["lightning_distance_mi"] is not None else None,
    }


@router.get("/local")
async def get_local_weather() -> dict:
    row = await get_latest_weather_local()
    if row is None:
        raise HTTPException(status_code=404, detail="No local weather data yet")
    return _row_to_dict_local(row)


@router.get("/local/history")
async def get_local_history(days: int = 7) -> list[dict]:
    rows = await get_weather_local_history(days)
    return [_row_to_dict_local(r) for r in rows]


@router.get("/regional/{region}")
async def get_regional_weather(region: str) -> dict:
    if region not in VALID_REGIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region. Valid: {', '.join(sorted(VALID_REGIONS))}",
        )
    row = await get_latest_weather_regional(region)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No data for region '{region}' yet")
    return {
        "time": row["time"].isoformat(),
        "region": row["region"],
        "temp_c": float(row["temp_c"]) if row["temp_c"] is not None else None,
        "precip_mm": float(row["precip_mm"]) if row["precip_mm"] is not None else None,
        "soil_moisture": float(row["soil_moisture"]) if row["soil_moisture"] is not None else None,
        "et0": float(row["et0"]) if row["et0"] is not None else None,
        "wind_speed_10m": float(row["wind_speed_10m"]) if row["wind_speed_10m"] is not None else None,
    }


@router.get("/local/rain-totals")
async def get_local_rain_totals() -> dict:
    return await get_rain_totals()


@router.get("/gdu")
async def gdu_status() -> dict:
    corn, beans = await get_gdu_status("corn"), await get_gdu_status("beans")
    return {"corn": corn, "beans": beans}


@router.get("/regional-history")
async def regional_history(days: int = 180) -> list[dict]:
    rows = await get_all_regional_history(days)
    return [
        {
            "time": r["time"].isoformat(),
            "region": r["region"],
            "temp_c": float(r["temp_c"]) if r["temp_c"] is not None else None,
            "precip_mm": float(r["precip_mm"]) if r["precip_mm"] is not None else None,
            "soil_moisture": float(r["soil_moisture"]) if r["soil_moisture"] is not None else None,
            "et0": float(r["et0"]) if r["et0"] is not None else None,
            "wind_speed_10m": float(r["wind_speed_10m"]) if r["wind_speed_10m"] is not None else None,
        }
        for r in rows
    ]


@router.get("/gdu/history")
async def gdu_history(days: int = 90) -> list[dict]:
    return await get_gdu_history(days)


# ── Planting dates ────────────────────────────────────────────────────────────

@router.get("/planting-dates")
async def list_planting_dates() -> list[dict]:
    rows = await get_planting_dates()
    return [
        {
            "commodity": r["commodity"],
            "year": r["year"],
            "planted_date": r["planted_date"].isoformat(),
            "notes": r["notes"],
        }
        for r in rows
    ]


@router.put("/planting-dates/{commodity}/{year}")
async def set_planting_date(commodity: str, year: int, body: PlantingDateBody) -> dict:
    if commodity not in VALID_CROPS:
        raise HTTPException(status_code=400, detail=f"Invalid crop. Valid: {', '.join(sorted(VALID_CROPS))}")
    await upsert_planting_date(
        commodity=commodity,
        year=year,
        planted_date=body.planted_date,
        notes=body.notes,
    )
    return {"commodity": commodity, "year": year, "planted_date": body.planted_date.isoformat()}


@router.delete("/planting-dates/{commodity}/{year}", status_code=204)
async def remove_planting_date(commodity: str, year: int) -> None:
    await delete_planting_date(commodity, year)
