# Session Notes

## Session: 2026-04-23

### What was done
- Built `farm_platform/feeds/elevator_scraper.py` -- ported from the operator's
  existing grainsignals repo (https://github.com/dbusch78/grainsignals).

**Key design decisions:**
- Auth uses Selenium headless Chrome (same approach as grainsignals) but runs in
  `asyncio.to_thread()` to avoid blocking the async event loop.
- Cookie persistence: pickled to `.cache/elevator_cookies.pkl`, reused between
  scrapes, refreshed automatically on 401/403.
- HTTP fetch uses `httpx.AsyncClient` (already in deps) with the Selenium cookies.
- Parsing is pure functions -- `_parse(json_data, elevator_names)` with no I/O,
  fully unit-tested (15 tests, all passing).
- Selenium and webdriver-manager added as optional dep group `[elevator]`.
- New config section `ElevatorSettings` (env prefix `ELEVATOR_`) added to
  `farm_platform/config.py`.
- APScheduler job `elevator_scraper` wired into `backend/main.py` on `ELEVATOR_SCRAPER_INTERVAL_HRS`.
- `.env.example` updated with all new ELEVATOR_* keys.

**What goes in .env to activate:**
```
ELEVATOR_RVC_EMAIL=your@email.com
ELEVATOR_RVC_PASSWORD=yourpassword
ELEVATOR_CASH_BIDS_URL=https://shop.rivervalleycoop.com/api/cash-bids  # (exact URL from browser devtools)
ELEVATOR_NAMES=Toulon  # (exact name as it appears in the API response)
```

**Note:** The actual `ELEVATOR_CASH_BIDS_URL` needs to be confirmed from the
browser DevTools Network tab when logged into the RVC site. The old grainsignals
repo stored it in `CASH_BIDS_URL` env var.

### What comes next (Milestone 1 remaining)
- [ ] Milestone 1 acceptance tests (requires running Docker stack):
      TimescaleDB receiving futures prices, WebSocket broadcasting, scenario model
      returning correct values via API
- [ ] `scripts/seed_positions.py` -- enter existing positions
- Optionally: confirm CASH_BIDS_URL by inspecting browser network tab logged
  into RVC site

### What comes after (Milestone 2 -- Frontend)
- Next.js 15 init, Tailwind dark theme, TypeScript API client
- HedgeCard, WeatherCard (placeholder), AgentCard (placeholder), DayTradingCard,
  CongressionalCard
- TradingView Lightweight Charts for price + basis chart
- Scenario modeler UI
- Grafana dashboards (futures OHLC, basis history, net effective price)

---

## Session: 2026-04-22

### What was done
- First commit. Built the entire Milestone 0 repository foundation and Milestone 1
  backend from scratch (v2.0 architecture per CLAUDE_CODE_BRIEF.md).

**Architecture note:** Package directory is `farm_platform/` (not `platform/` as the brief
shows) because `platform` is a Python stdlib module and naming a local package the same
breaks setuptools and any package that imports it. All imports use `farm_platform.*`.

**Milestone 0 -- Repository (code tasks done):**
- `.gitignore` with `data/`, `node_modules/`, standard Python patterns
- `pyproject.toml` -- full v2.0 dependency list (FastAPI, asyncpg, motor, APScheduler,
  anthropic, yfinance, polars, structlog, websockets, alpaca-py optional, dev extras)
- `.env.example` -- all keys documented (Anthropic, Ambient, Alpaca paper+live,
  NewsAPI, Finnhub, Quiver, TimescaleDB, MongoDB, Grafana, farm config)
- `docker-compose.yml` -- all services (NPM, TimescaleDB, MongoDB, FastAPI, Next.js, Grafana)

**Milestone 0 -- DB Init:**
- `scripts/init_db.py` -- creates TimescaleDB hypertables + MongoDB collections + indexes

**Milestone 1 -- Core data + hedge tracker backend:**
- `farm_platform/config.py` -- pydantic-settings config (all service sections)
- `farm_platform/storage/schemas.sql` -- full DDL: futures_prices, cash_prices,
  options_snapshots, weather_station_local, weather_regional, gdu_daily materialized view
- `farm_platform/storage/timescale.py` -- asyncpg pool, upsert/query helpers
- `farm_platform/storage/mongo.py` -- motor client, positions CRUD, agent_run helpers,
  trading mode audit, elevator snapshots, _serialize(ObjectId→str)
- `farm_platform/feeds/futures_feed.py` -- yfinance ZC=F/ZS=F/ZW=F, stale flag,
  WebSocket callback registration, APScheduler job
- `farm_platform/hedge/calculator.py` -- Phase 1/2 net effective price (pure functions)
- `farm_platform/hedge/scenario_model.py` -- scenario table for hypothetical prices
- `farm_platform/hedge/tracker.py` -- MongoDB CRUD for positions (add, get, list, update,
  close, phase 2 transition)
- `backend/main.py` -- FastAPI app, CORS, startup/shutdown hooks, APScheduler wired
- `backend/websocket.py` -- /ws/prices WebSocket broadcaster
- `backend/models/hedge.py` -- Pydantic request/response schemas
- `backend/routers/hedge.py` -- All hedge endpoints:
  GET/POST /api/hedge/positions, GET/PUT /api/hedge/positions/{id},
  GET /api/hedge/net-price, POST /api/hedge/scenario,
  GET /api/hedge/prices/futures, GET /api/hedge/prices/cash
- `tests/platform/` -- 15 unit tests for calculator + scenario model (all pass)

### What comes next (Milestone 1 remaining)
- [ ] Elevator scraper (`farm_platform/feeds/elevator_scraper.py`) -- port operator's
      existing scraper, standardise output, write to cash_prices + MongoDB snapshots
- [ ] Unit test: verify basis calculation
- [ ] Milestone 1 acceptance tests (requires running Docker stack):
      TimescaleDB receiving futures prices, WebSocket broadcasting, scenario model
      returning correct values via API
- [ ] `scripts/seed_positions.py` -- enter existing positions

### What comes after (Milestone 2 -- Frontend)
- Next.js 15 init, Tailwind dark theme, TypeScript API client
- HedgeCard, WeatherCard (placeholder), AgentCard (placeholder), DayTradingCard,
  CongressionalCard
- TradingView Lightweight Charts for price + basis chart
- Scenario modeler UI
- Grafana dashboards (futures OHLC, basis history, net effective price)

### Known deviations from brief
1. Package name `farm_platform/` instead of `platform/` -- stdlib name collision.
2. `src/` directory from v1 scaffolding left in place untracked (not committed).
