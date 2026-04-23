"""River Valley Co-op cash bid scraper.

Fetches cash bids from the RVC JSON API using cookie-based auth (Selenium
login on first run, cookie reuse thereafter), parses prices for configured
elevator locations, writes each bid row to the cash_prices hypertable, and
saves the full raw response to MongoDB elevator_snapshots.

Requires optional deps: pip install farm-platform[elevator]
"""

from __future__ import annotations

import asyncio
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from farm_platform.config import settings
from farm_platform.storage.mongo import save_elevator_snapshot
from farm_platform.storage.timescale import insert_cash_price

log = structlog.get_logger(__name__)

# Maps API commodity_name (lower) → canonical DB value
_COMMODITY_MAP: dict[str, str] = {
    "corn": "corn",
    "soybeans": "soybeans",
    "soybean": "soybeans",
}


# ── Cookie persistence ────────────────────────────────────────────────────────

def _cookie_path() -> Path:
    path = Path(settings.elevator.cookie_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_cookies() -> list[dict[str, Any]] | None:
    path = _cookie_path()
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            return pickle.load(f)  # type: ignore[no-any-return]
    except Exception as exc:
        log.warning("elevator_cookie_load_failed", error=str(exc))
        return None


def _save_cookies(cookies: list[dict[str, Any]]) -> None:
    try:
        with _cookie_path().open("wb") as f:
            pickle.dump(cookies, f)
        log.debug("elevator_cookies_saved", count=len(cookies))
    except Exception as exc:
        log.error("elevator_cookie_save_failed", error=str(exc))


# ── Selenium auth (blocking — runs in thread) ─────────────────────────────────

def _find_chromedriver(wdm_path: str) -> str | None:
    """Locate the actual chromedriver binary given webdriver-manager's path."""
    p = Path(wdm_path)
    if p.is_file() and p.name == "chromedriver":
        os.chmod(p, 0o755)
        return str(p)
    search_root = p if p.is_dir() else p.parent
    for candidate in [search_root, search_root.parent]:
        if candidate.is_dir():
            found = list(candidate.glob("**/chromedriver"))
            if found:
                os.chmod(found[0], 0o755)
                return str(found[0])
    return None


def _selenium_authenticate() -> list[dict[str, Any]] | None:
    """Authenticate with RVC using headless Selenium. Returns cookie list or None."""
    try:
        import random
        import time as _time
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        log.error(
            "elevator_auth_deps_missing",
            hint="pip install farm-platform[elevator]",
        )
        return None

    email = settings.elevator.rvc_email
    password = settings.elevator.rvc_password
    rvc_base = settings.elevator.rvc_base

    if not email or not password:
        log.error("elevator_auth_no_credentials")
        return None

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        wdm_path = ChromeDriverManager().install()
        driver_path = _find_chromedriver(wdm_path)
        if driver_path is None:
            log.error("elevator_chromedriver_not_found", wdm_path=wdm_path)
            return None

        driver = webdriver.Chrome(service=Service(driver_path), options=options)
        driver.set_page_load_timeout(60)

        login_url = f"{rvc_base}/sign-in?next=%2Fcommodity-prices%2Fcash_bids"
        driver.get(login_url)
        _time.sleep(random.uniform(1.5, 3.0))

        wait = WebDriverWait(driver, 60)

        email_field = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@placeholder='Email or Mobile Number']")
            )
        )
        email_field.clear()
        email_field.send_keys(email)

        next_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Next')]")
            )
        )
        next_btn.click()
        _time.sleep(random.uniform(1.5, 2.5))

        pw_field = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
        )
        pw_field.send_keys(password)
        pw_field.send_keys(Keys.RETURN)

        wait.until(lambda d: "cash_bids" in d.current_url)
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(text(), 'Cash Bids') and contains(@class, 'active')]")
            )
        )

        cookies = driver.get_cookies()
        log.info("elevator_auth_ok", cookie_count=len(cookies))
        return cookies  # type: ignore[return-value]

    except Exception as exc:
        log.error("elevator_auth_failed", error=str(exc))
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ── HTTP fetch ────────────────────────────────────────────────────────────────

async def _fetch(cookies: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Fetch cash bids JSON using cookie auth. Returns None if auth expired."""
    url = settings.elevator.cash_bids_url
    if not url:
        log.error("elevator_no_cash_bids_url")
        return None

    cookie_dict = {
        c["name"]: c["value"]
        for c in cookies
        if c.get("name") and c.get("value")
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, cookies=cookie_dict, headers=headers)

        if resp.status_code in (401, 403):
            log.warning("elevator_cookies_expired", status=resp.status_code)
            return None  # Caller will re-auth

        resp.raise_for_status()
        data: dict[str, Any] | list[Any] = resp.json()
        # Normalise: API may return a bare list
        if isinstance(data, list):
            return {"locations": data}
        return data  # type: ignore[return-value]

    except Exception as exc:
        log.error("elevator_fetch_error", error=str(exc))
        return None


async def _authenticated_fetch() -> dict[str, Any] | None:
    """Fetch cash bids, refreshing cookies via Selenium if needed."""
    cookies = _load_cookies()
    if cookies:
        data = await _fetch(cookies)
        if data is not None:
            return data

    log.info("elevator_reauth_starting")
    cookies = await asyncio.to_thread(_selenium_authenticate)
    if not cookies:
        log.error("elevator_reauth_failed")
        return None

    _save_cookies(cookies)
    return await _fetch(cookies)


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse(
    json_data: dict[str, Any],
    elevator_names: list[str],
) -> tuple[list[dict[str, Any]], datetime]:
    """
    Extract bid rows for the configured elevators.

    Returns (records, scraped_at).  Each record dict matches insert_cash_price kwargs
    (minus `time` which uses scraped_at).
    """
    from dateutil import parser as _dp  # local import: optional dep

    names_lower = {n.lower(): n for n in elevator_names}
    records: list[dict[str, Any]] = []
    latest_created: datetime | None = None

    for location in json_data.get("locations", []):
        loc_name = (location.get("name") or "").strip()
        canonical = names_lower.get(loc_name.lower())
        if canonical is None:
            continue

        for commodity_obj in location.get("commodities", []):
            raw_com = (commodity_obj.get("commodity_name") or "").strip().lower()
            commodity = _COMMODITY_MAP.get(raw_com)
            if commodity is None:
                continue

            for bid in commodity_obj.get("cash_bids", []):
                # Track latest API-side created timestamp
                created_str = bid.get("created")
                if created_str:
                    try:
                        ts = _dp.parse(created_str).astimezone(timezone.utc)
                        if latest_created is None or ts > latest_created:
                            latest_created = ts
                    except Exception:
                        pass

                try:
                    cash_price = float(bid["cash_price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if cash_price <= 0:
                    continue

                futures_ref: float | None = None
                try:
                    if bid.get("futures_price"):
                        futures_ref = float(bid["futures_price"])
                except (TypeError, ValueError):
                    pass

                basis: float | None = None
                try:
                    if bid.get("basis"):
                        basis = float(bid["basis"])
                except (TypeError, ValueError):
                    pass

                records.append({
                    "elevator": canonical,
                    "commodity": commodity,
                    "cash_price": cash_price,
                    "futures_ref": futures_ref,
                    "basis": basis,
                    "contract_month": bid.get("contract_date") or None,
                })

    scraped_at = latest_created or datetime.now(tz=timezone.utc)
    return records, scraped_at


# ── Public API ────────────────────────────────────────────────────────────────

async def run_once() -> None:
    """Scrape cash bids and persist to TimescaleDB + MongoDB. Called by scheduler."""
    elevator_names = settings.elevator.elevator_list
    if not elevator_names:
        log.warning("elevator_no_names_configured")
        return

    json_data = await _authenticated_fetch()
    if json_data is None:
        log.error("elevator_scrape_aborted_no_data")
        return

    # Raw snapshot to MongoDB for historical record
    await save_elevator_snapshot(
        {
            "raw_response": json_data,
            "elevator_names_requested": elevator_names,
        }
    )

    records, scraped_at = _parse(json_data, elevator_names)
    if not records:
        log.warning("elevator_no_records_for_configured_elevators", names=elevator_names)
        return

    time_str = scraped_at.isoformat()
    stored = 0
    for rec in records:
        try:
            await insert_cash_price(
                time=time_str,
                elevator=rec["elevator"],
                commodity=rec["commodity"],
                cash_price=rec["cash_price"],
                futures_ref=rec["futures_ref"],
                basis=rec["basis"],
                contract_month=rec["contract_month"],
            )
            stored += 1
        except Exception:
            log.exception(
                "elevator_insert_failed",
                elevator=rec["elevator"],
                commodity=rec["commodity"],
            )

    log.info("elevator_scrape_done", stored=stored, total=len(records))


def scheduled_scrape() -> None:
    """Synchronous entry point for APScheduler."""
    asyncio.get_event_loop().run_until_complete(run_once())
