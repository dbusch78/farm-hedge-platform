# Session Notes

## Session: 2026-04-27

### What was done
- Rewrote `README.md` -- full install/run/test instructions for both environments
  (WSL/Windows dev and Ubuntu VM production). Covers prerequisites, first-time setup,
  NPM proxy config, DNS setup per environment, local dev without Docker, running tests,
  Milestone 2 acceptance checklist, and daily ops commands.
- Fixed `backend/Dockerfile` -- was copying `platform/` (does not exist); corrected to
  `farm_platform/`.
- Created `frontend/Dockerfile` -- was missing; multi-stage Node 24 Alpine build using
  Next.js standalone output mode.
- Added `output: "standalone"` to `frontend/next.config.ts` (required by the Dockerfile).

**RVC elevator scraper -- FUTURES_URL support:**
- Operator confirmed RVC also exposes a futures quotes endpoint:
  `https://shop.rivervalleycoop.com/api/v1/commodity/futures`
- NOTE: The cash bids API (`ELEVATOR_CASH_BIDS_URL`) already returns `basis` and
  `futures_price` fields on each bid row -- basis is read directly from the API,
  NOT calculated from yfinance math. The futures URL is an additional/redundant source.
- Added `ELEVATOR_FUTURES_URL` to `ElevatorSettings` in `farm_platform/config.py`.
- Added `ELEVATOR_FUTURES_URL` to `.env.example` (pre-filled with the known URL).
- Refactored `elevator_scraper.py`:
  - `_fetch_url(url, cookies)` -- generic authenticated GET replacing the old
    cash-bids-only `_fetch()`
  - `_fetch(cookies)` -- fires both URLs in parallel via `asyncio.gather`; returns
    `(cash_data, futures_data)` tuple; futures fetch skipped gracefully if URL not set
  - `run_once()` -- folds `futures_response` into the MongoDB snapshot alongside
    `raw_response` when futures data is available

### What comes next (Milestone 2 remaining -- needs Docker stack)
- [ ] Mobile layout verified on phone over VPN
- [ ] `farm.local` loads and hedge card shows live prices
- [ ] WebSocket price updates verified without page refresh
- [ ] Scenario modeler tested with real data
- [ ] TradingView chart renders with real OHLC data

---

## Session: 2026-04-23 (continued)

### What was done
- Wrote `scripts/seed_positions.py` -- interactive CLI script to insert existing
  positions into MongoDB. Takes `--dry-run` and `--clear` flags. Has example
  position templates commented out for the operator to fill in.
- Bootstrapped Next.js 16 / Tailwind v4 frontend in `frontend/`. Key notes:
  - Node.js 24.15 / Next.js 16.2.4 / Tailwind v4 (CSS-based config, no tailwind.config.ts)
  - Tailwind v4 uses `@theme inline` in `globals.css` -- not `tailwind.config.ts`
  - Params in dynamic routes are now `Promise<{...}>` -- must `await params`
  - TypeScript strict, `@/*` path alias

**Files created:**
- `frontend/app/globals.css` -- full dark theme via CSS variables + `@theme inline`
- `frontend/lib/types.ts` -- all TypeScript types matching FastAPI Pydantic models
- `frontend/lib/api.ts` -- typed fetch wrapper for all API endpoints
- `frontend/hooks/useFuturesPrices.ts` -- WebSocket hook with auto-reconnect,
  stale detection (60s), and exponential backoff
- `frontend/components/cards/HedgeCard.tsx` -- full Phase 1/2 card with live
  WebSocket price updates, P&L, premium cost line, delta-adj contract counts
- `frontend/components/cards/WheatCard.tsx` -- ZW leading indicator card
- `frontend/components/cards/AgentCard.tsx` -- positioning advisor output card
- `frontend/components/cards/WeatherCard.tsx` -- placeholder (Milestone 3)
- `frontend/components/cards/DayTradingCard.tsx` -- paper/live badge, disabled
  Go Live button (Milestone 5)
- `frontend/components/cards/CongressionalCard.tsx` -- placeholder (Milestone 6)
- `frontend/app/layout.tsx` -- dark shell, sticky top nav, footer
- `frontend/app/page.tsx` -- server component dashboard: fetches positions,
  futures prices, net prices, trading mode, latest agent run in parallel;
  falls back gracefully when backend is offline
- `frontend/.env.local` -- dev env pointing to localhost:8000

**Dependencies installed:** `lightweight-charts@5.1.0`, `lucide-react@1.8.0`, `zustand@5.0.12`

**TypeScript check:** passing (exit 0)

### Session 2 continued (same day) -- Milestone 2 frontend complete

**Backend fixes:**
- `farm_platform/storage/timescale.py`: added `get_futures_history(symbol, days)` query
- `backend/routers/hedge.py`: added `GET /api/hedge/prices/history/{symbol}?days=N` endpoint
- `lib/api.ts`: fixed prices routes (were missing `/hedge/` prefix), fixed `getNetPrice`
  to return `null` not throw (backend returns a list, not filtered by commodity)

**Frontend -- new files:**
- `frontend/components/charts/PriceChart.tsx` -- TradingView Lightweight Charts v5
  candlestick + basis line overlay + strike + net-eff price horizontal lines.
  NOTE: v5 exports are PascalCase: `CandlestickSeries`, `LineSeries` (not camelCase).
  The typings.d.ts shows camelCase but runtime exports are PascalCase -- Turbopack
  correctly rejected the camelCase imports.
- `frontend/components/trading/ScenarioModeler.tsx` -- full scenario table with
  min/max/steps inputs, highlights current futures price row and at-strike row
- `frontend/components/trading/PositionEntry.tsx` -- all fields, live delta-adj
  contract count display, Phase 2 cash_sale_price field appears when type = call
- `frontend/app/hedge/page.tsx` -- server component: fetches positions, prices,
  net prices, OHLC history in parallel; renders CommoditySection for ZC and ZS
  each with chart + position list + scenario modeler; Add Position form at bottom

**Build:** clean (`npm run build` exit 0, both `/` and `/hedge` routes compile)

### What comes next (Milestone 2 remaining -- needs Docker stack)
- [ ] Mobile layout verified on phone over VPN
- [ ] `farm.local` loads and hedge card shows live prices
- [ ] WebSocket price updates verified without page refresh
- [ ] Scenario modeler tested with real data
- [ ] TradingView chart renders with real OHLC data

### After Milestone 2 acceptance (Milestone 2 Grafana -- needs Docker)
- [ ] Connect Grafana to TimescaleDB, build 3 dashboards (futures OHLC, basis history,
  net effective price), export JSONs to `grafana/provisioning/dashboards/`

### What comes next after that (Milestone 3 -- Weather)
- `platform/feeds/ambient_feed.py` -- Ambient Weather WebSocket + REST
- `platform/feeds/openmeteo_feed.py` -- 4 regions (corn belt, MT/PR/pampas)
- `platform/feeds/gdu_calculator.py` -- GDU from planting date
- `platform/feeds/weather_service.py` -- internal service for agents
- FastAPI weather routes + WeatherCard real data + Grafana weather dashboards

---

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
