# Farm Hedge + Day Trading Platform
## Claude Code Project Brief -- v2.0

**Author:** Project Owner (Director of Information Security / Corn & Soybean Farmer, Western Illinois)  
**Purpose:** Personal-use commodity hedging, day trading sandbox, and long-term portfolio tracker  
**Primary Goal:** Replace crop risk management advisory services with a self-operated, AI-augmented platform  
**Updated:** Reflects full UI architecture, Next.js 15 frontend, FastAPI backend, Nginx Proxy Manager, Proxmox/Ubuntu/Docker infrastructure, Ubiquiti Dream Machine VPN

---

## Table of Contents

1. [Project Context](#1-project-context)
2. [Guiding Principles](#2-guiding-principles)
3. [Infrastructure & Network Architecture](#3-infrastructure--network-architecture)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Data Layer](#6-data-layer)
7. [AI Agent Layer](#7-ai-agent-layer)
8. [Application Modules](#8-application-modules)
9. [Frontend UI Design](#9-frontend-ui-design)
10. [Milestones & Task Checklist](#10-milestones--task-checklist)
11. [API Credentials Needed](#11-api-credentials-needed)
12. [Known Constraints & Failure Modes](#12-known-constraints--failure-modes)
13. [Future Expansion](#13-future-expansion)

---

## 1. Project Context

### Who This Is For

The operator is a corn and soybean farmer in western Illinois who also works professionally as a Director of Information Security with 22 years of IT and coding experience. This is a personal-use platform, not a commercial product. Treat all code as production-quality but personal-scale. No need for multi-tenancy, SaaS patterns, or generic disclaimers. The operator understands markets, farming, and infrastructure deeply -- write code accordingly.

### The Core Farming Problem

The operator has no on-farm grain storage. At harvest, grain is delivered directly to the local co-op and sold at whatever the cash price is that day -- a forced-seller position. The goal is to use CBOT exchange-traded options to create a price floor before harvest and capture upside after the physical grain is sold, without paying a crop risk management advisory firm to do it.

### Two-Phase Hedging Strategy

**Phase 1 -- Pre-Sale Floor (crop in the ground or at co-op, not yet sold)**
- Buy put options on July ZC (corn) and/or July ZS (soybean) contracts
- If cash prices fall, puts gain value and offset the loss on physical grain
- Remain in puts until physical grain is sold to the elevator

**Phase 2 -- Post-Sale Upside Capture (physical grain sold, cash received)**
- Close any remaining puts
- Open call options on the same or nearby contract month
- No longer have physical price exposure; calls allow participation in any rally
- Hold calls until target price is hit, expiration approaches, or a defined exit rule triggers

**The North Star Metric:**
```
Net Effective Price Per Bushel = Cash Sale Price + Options P&L (net of premiums paid)
```
Every view, card, chart, and agent output anchors back to this number. Premium paid is always visible as a cost -- never hidden.

---

## 2. Guiding Principles

1. **MVP first.** Build the smallest working version of each module, then expand. Do not over-engineer before the core works.
2. **Modular architecture.** Each module is independently runnable and testable. Frontend, backend, data feeds, and agents are all decoupled.
3. **Everything owned locally.** All data lives in local Docker containers on the operator's Proxmox VM. No cloud storage dependencies.
4. **Retrospective capability is first-class.** Store raw inputs AND agent outputs together. Agent performance must be evaluable and tunable over time using historical data.
5. **Free tiers first.** Flag explicitly when a paid tier becomes necessary.
6. **Clean Python throughout (backend).** PEP 8, type hints, docstrings on all public functions. Modular files, not monoliths.
7. **Clean TypeScript throughout (frontend).** Typed API client, typed component props. No `any`.
8. **Security-aware by default.** All credentials in `.env` files, never hardcoded. `.env` in `.gitignore`. Containers do not expose ports to 0.0.0.0 -- bind to LAN IP only. Access controlled via existing Ubiquiti VPN infrastructure.
9. **Server owns all state that matters.** Trading mode (paper vs. live), alert acknowledgments, and position data are server-side. Browser state is display only.

---

## 3. Infrastructure & Network Architecture

### Physical Setup

```
┌──────────────────────────────────────────────────────────────────────┐
│                        OPERATOR DEVICES                              │
│                                                                      │
│   iPhone / Android         MacBook / Windows Laptop                  │
│   (combine cab, field)     (office / home)                           │
│         │                          │                                 │
└─────────┼──────────────────────────┼─────────────────────────────────┘
          │                          │
          │    Ubiquiti Dream Machine VPN (existing)                   
          │    WireGuard / Ubiquiti SSL VPN                            
          │    Routes remote devices into LAN segment                  
          │                          │
          ▼                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    HOME LAN (Ubiquiti managed)                       │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Proxmox Host                                    │    │
│  │                                                              │    │
│  │   ┌──────────────────────────────────────────────────────┐  │    │
│  │   │  Ubuntu 24.04 LTS VM  (static LAN IP via UniFi DHCP │  │    │
│  │   │  reservation or static assignment in Ubuntu)         │  │    │
│  │   │  Recommended: 4 vCPU / 8GB RAM / 100GB thin disk    │  │    │
│  │   │                                                      │  │    │
│  │   │   Docker Compose                                     │  │    │
│  │   │   ├── nginx-proxy-manager  :80 :443 :81             │  │    │
│  │   │   ├── nextjs               :3000                     │  │    │
│  │   │   ├── fastapi              :8000                     │  │    │
│  │   │   ├── timescaledb          :5432                     │  │    │
│  │   │   ├── mongodb              :27017                    │  │    │
│  │   │   └── grafana              :3001                     │  │    │
│  │   └──────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### DNS Setup (UniFi Network --> DNS)

Set these local DNS records in the UniFi controller so all devices on LAN and VPN resolve cleanly:

| Hostname | Points To | Service |
|---|---|---|
| `farm.local` | VM LAN IP | Next.js dashboard |
| `api.farm.local` | VM LAN IP | FastAPI backend |
| `npm.farm.local` | VM LAN IP | Nginx Proxy Manager admin UI |

All routing handled by Nginx Proxy Manager. One IP, clean hostnames, no port numbers on mobile.

### Nginx Proxy Manager

Run as a Docker container. Provides:
- Reverse proxy from hostnames to internal container ports
- Optional SSL via self-signed cert (nice-to-have for the green lock on mobile)
- Web admin UI at `npm.farm.local:81` for configuration
- No manual Nginx config file editing needed

```yaml
# Proxy host entries to configure in NPM admin UI:
# farm.local          --> nextjs:3000
# api.farm.local      --> fastapi:8000
# (npm.farm.local:81 is NPM's own admin, no proxy needed)
```

### Container Network Isolation

TimescaleDB and MongoDB must NOT be exposed on the host network interface. They communicate only on the internal Docker bridge network. Only the following ports bind to the host (VM LAN IP):

| Container | Host Port | Accessible At |
|---|---|---|
| nginx-proxy-manager | 80, 443, 81 | Handles all external routing |

All other containers (Next.js, FastAPI, TimescaleDB, MongoDB) communicate internally on the Docker network only.

---

## 4. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                 │
├─────────────────┬───────────────────┬────────────────────────────────┤
│  MARKET PRICES  │     WEATHER       │        INTELLIGENCE            │
│                 │                   │                                │
│ yfinance        │ Ambient Weather   │ USDA WASDE (PDF releases)      │
│  ZC=F  corn     │  Direct REST API  │ CONAB monthly (Brazil)         │
│  ZS=F  beans    │  WebSocket push   │ Rosario Grain Exchange (Arg.)  │
│  ZW=F  wheat    │  (no HA dep.)     │ Pre-report private estimates   │
│                 │                   │  (StoneX, Allendale)           │
│ Local elevator  │ Open-Meteo        │                                │
│  scraper        │  Corn Belt        │ NewsAPI / Finnhub headlines     │
│  (operator-     │  Mato Grosso BR   │ Quiver Quantitative            │
│   built)        │  Parana BR        │  congressional trades          │
│                 │  Pampas AR        │                                │
│ Alpaca API      │                   │                                │
│  equities       │                   │                                │
│  paper + live   │                   │                                │
└─────────────────┴───────────────────┴────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                               │
├──────────────────────────────┬───────────────────────────────────────┤
│  TimescaleDB (Postgres 16)   │  MongoDB 7                            │
│                              │                                       │
│  Time-series data:           │  Document / event data:               │
│  • ZC/ZS/ZW OHLCV prices     │  • USDA WASDE raw releases            │
│  • Local cash prices + basis │  • CONAB / Rosario reports            │
│  • Options P&L snapshots     │  • News articles + sentiment          │
│  • Weather all regions       │  • AI agent outputs + reasoning       │
│  • On-farm station telemetry │  • Agent prompt version history       │
│  • GDU daily accumulation    │  • Elevator scrape snapshots          │
│                              │  • Trade journal entries              │
│                              │  • Operator annotations               │
│                              │  • Trading mode audit log             │
└──────────────────────────────┴───────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       AI AGENT LAYER                                 │
│  Agent 1: USDA Skeptic        Agent 2: South America Monitor        │
│  Agent 3: Weather Analyst     Agent 4: News Sentiment Filter        │
│  Agent 5: Positioning Advisor (synthesizes 1-4 + current position)  │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND  (:8000)                         │
│  /api/hedge    /api/agents    /api/weather    /api/daytrading        │
│  /api/portfolio               /ws/prices  (WebSocket)                │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│              PRESENTATION LAYER                                      │
├──────────────────────────────┬───────────────────────────────────────┤
│              Next.js 15  (farm.local)                                │
│                                                                      │
│  Card-based dark UI          TradingView Lightweight Charts          │
│  Interactive tools           Price history, basis trends             │
│  Mobile responsive           P&L over time, weather history          │
│  Paper / Live toggle         Agent accuracy retrospective            │
│                              GDU accumulation charts                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technology Stack

### Backend

| Component | Technology | Notes |
|---|---|---|
| Language | Python 3.12+ | Throughout, PEP 8, type hints required |
| API framework | FastAPI | Async, WebSocket support, auto OpenAPI docs |
| Time-series DB | TimescaleDB (Postgres 16 ext.) | Native SQL, hypertables, continuous aggregates |
| Document DB | MongoDB 7 | Agent outputs, reports, journal, audit log |
| Task scheduling | APScheduler | Lightweight, no Celery overhead |
| AI agents | Anthropic Claude API | claude-sonnet-4-20250514, per-token billing |
| Brokerage | Alpaca API | Paper free tier; live when ready |
| Market data | yfinance | ZC=F, ZS=F, ZW=F delayed quotes |
| Weather (farm) | Ambient Weather API | Direct WebSocket, no Home Assistant dependency |
| Weather (regional) | Open-Meteo | Free, ECMWF/GFS, global coverage |
| News | NewsAPI + Finnhub | Free tiers, headlines and IPO calendar |
| Congressional | Quiver Quantitative | Free tier, disclosed trades |
| HTTP client | httpx (async) | Async-native, used throughout |
| Data processing | polars | Faster than pandas for time-series operations |
| Config | pydantic-settings + .env | Type-safe, secrets never hardcoded |
| Logging | structlog | JSON-structured, queryable |
| Testing | pytest + pytest-asyncio | Full async test support |

### Frontend

| Component | Technology | Notes |
|---|---|---|
| Framework | Next.js 15 (App Router) | SSR for fast mobile load, file-based routing |
| Language | TypeScript | Strict mode, no `any` |
| Styling | Tailwind CSS | Dark theme, utility-first, responsive |
| Charts | TradingView Lightweight Charts | Professional OHLC/candlestick, free open source |
| UI components | shadcn/ui | Accessible, Tailwind-native, no heavy deps |
| State management | Zustand | Lightweight, sufficient for this scale |
| API client | Custom typed fetch wrapper over FastAPI | Generated from OpenAPI spec |
| Real-time prices | WebSocket (native browser API) | Connects to FastAPI /ws/prices |
| Icons | Lucide React | Consistent, Tailwind-compatible |

### Infrastructure

| Component | Technology | Notes |
|---|---|---|
| Host | Proxmox VM -- Ubuntu 24.04 LTS | 4 vCPU / 8GB RAM / 100GB thin provisioned |
| Containers | Docker + Docker Compose | All services containerized |
| Reverse proxy | Nginx Proxy Manager | Docker container, web UI config, hostname routing |
| DNS | UniFi Network controller | Local DNS records for *.farm.local hostnames |
| VPN | Ubiquiti Dream Machine (existing) | Operator's existing infrastructure, no changes needed |
| Backups | pg_dump + mongodump via cron | Daily, to operator's existing backup infrastructure |

---

## 6. Data Layer

### 6.1 Repository Structure

```
farm_platform/
├── .env                            # Credentials -- in .gitignore
├── .env.example                    # Template, all keys documented
├── docker-compose.yml
├── pyproject.toml
├── README.md
│
├── data/                           # Docker volumes -- gitignored
│   ├── timescale/
│   ├── mongo/
│   └── grafana/
│
├── backend/                        # FastAPI application
│   ├── main.py                     # App init, router registration, WebSocket
│   ├── routers/
│   │   ├── hedge.py
│   │   ├── agents.py
│   │   ├── weather.py
│   │   ├── daytrading.py
│   │   └── portfolio.py
│   ├── services/                   # Business logic -- imports from platform/
│   │   ├── hedge_service.py
│   │   ├── agent_service.py
│   │   └── trading_service.py
│   ├── models/                     # Pydantic request/response schemas
│   │   ├── hedge.py
│   │   ├── agents.py
│   │   ├── weather.py
│   │   └── trading.py
│   └── websocket.py                # Price broadcast manager
│
├── platform/                       # Core Python modules (no FastAPI dependency)
│   ├── config.py                   # pydantic-settings loader
│   │
│   ├── feeds/                      # Data ingestion
│   │   ├── futures_feed.py         # yfinance ZC=F ZS=F ZW=F
│   │   ├── elevator_scraper.py     # Operator's existing scraper
│   │   ├── ambient_feed.py         # Ambient Weather WebSocket
│   │   ├── openmeteo_feed.py       # Regional weather
│   │   ├── usda_feed.py            # WASDE fetch and parse
│   │   ├── conab_feed.py           # Brazilian crop reports
│   │   └── news_feed.py            # NewsAPI / Finnhub
│   │
│   ├── storage/                    # DB abstraction layer
│   │   ├── timescale.py            # TimescaleDB client
│   │   ├── mongo.py                # MongoDB client
│   │   └── schemas.sql             # Full DDL
│   │
│   ├── agents/                     # AI agent layer
│   │   ├── base_agent.py
│   │   ├── usda_skeptic.py
│   │   ├── sa_monitor.py
│   │   ├── weather_analyst.py
│   │   ├── news_filter.py
│   │   └── positioning_advisor.py
│   │
│   ├── hedge/                      # Hedge module logic
│   │   ├── tracker.py
│   │   ├── calculator.py
│   │   ├── scenario_model.py
│   │   └── alerts.py
│   │
│   ├── daytrading/                 # Day trading module logic
│   │   ├── watchlist.py
│   │   ├── ipo_tracker.py
│   │   ├── momentum_scanner.py
│   │   ├── alpaca_client.py        # Paper + live mode aware
│   │   └── trade_journal.py
│   │
│   └── portfolio/                  # Long-term portfolio logic
│       ├── congressional.py
│       ├── ledger.py
│       └── signal_alerts.py
│
├── frontend/                       # Next.js 15 application
│   ├── app/
│   │   ├── layout.tsx              # Dark shell, nav, live mode banner
│   │   ├── page.tsx                # Main dashboard
│   │   ├── hedge/
│   │   │   ├── page.tsx            # Hedge overview + scenario modeler
│   │   │   └── [id]/page.tsx       # Individual position detail
│   │   ├── journal/
│   │   │   └── page.tsx            # Trade history log
│   │   ├── agents/
│   │   │   └── page.tsx            # Agent runs + annotation UI
│   │   ├── weather/
│   │   │   └── page.tsx            # All weather panels
│   │   └── portfolio/
│   │       └── page.tsx
│   │
│   ├── components/
│   │   ├── cards/
│   │   │   ├── HedgeCard.tsx       # Phase 1/2 position card
│   │   │   ├── AgentCard.tsx       # Latest agent output card
│   │   │   ├── WeatherCard.tsx     # On-farm + regional summary
│   │   │   ├── DayTradingCard.tsx  # Paper/live status card
│   │   │   └── CongressionalCard.tsx
│   │   ├── charts/
│   │   │   ├── PriceChart.tsx      # TradingView candlestick
│   │   │   ├── BasisChart.tsx      # Cash vs futures, 3yr avg overlay
│   │   │   ├── PnLChart.tsx        # Net effective price over time
│   │   │   └── WeatherChart.tsx    # Rainfall, temp, GDU
│   │   ├── trading/
│   │   │   ├── LiveModeToggle.tsx  # See Section 9 for full spec
│   │   │   ├── OrderEntry.tsx
│   │   │   └── PositionEntry.tsx
│   │   └── ui/                     # shadcn/ui component overrides
│   │
│   ├── hooks/
│   │   ├── useFuturesPrices.ts     # WebSocket live price feed
│   │   ├── useHedgePositions.ts
│   │   └── useAgentRuns.ts
│   │
│   ├── lib/
│   │   ├── api.ts                  # Typed FastAPI client
│   │   └── types.ts                # Shared TypeScript types
│   │
│   └── tailwind.config.ts          # Dark theme tokens
│
├── scripts/
│   ├── init_db.py                  # First-run DB setup and DDL
│   ├── backfill_basis.py           # USDA AMS historical basis
│   └── seed_positions.py           # Enter existing positions
│
├── grafana/
│   └── provisioning/               # Dashboard JSON exports, auto-loaded
│       ├── datasources/
│       └── dashboards/
│
└── tests/
    ├── backend/
    ├── platform/
    └── feeds/
```

### 6.2 TimescaleDB Schema

```sql
-- Futures prices (ZC, ZS, ZW)
CREATE TABLE futures_prices (
    time            TIMESTAMPTZ NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    open            NUMERIC(10,4),
    high            NUMERIC(10,4),
    low             NUMERIC(10,4),
    close           NUMERIC(10,4),
    volume          BIGINT,
    source          VARCHAR(20) DEFAULT 'yfinance',
    stale           BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('futures_prices', 'time');
CREATE INDEX ON futures_prices (symbol, time DESC);

-- Local cash prices and basis
CREATE TABLE cash_prices (
    time            TIMESTAMPTZ NOT NULL,
    elevator        VARCHAR(100) NOT NULL,
    commodity       VARCHAR(20) NOT NULL,
    cash_price      NUMERIC(8,4) NOT NULL,
    futures_ref     NUMERIC(8,4),
    basis           NUMERIC(8,4),
    contract_month  VARCHAR(10)
);
SELECT create_hypertable('cash_prices', 'time');

-- Options position P&L snapshots
CREATE TABLE options_snapshots (
    time            TIMESTAMPTZ NOT NULL,
    position_id     VARCHAR(50) NOT NULL,
    underlying_px   NUMERIC(10,4) NOT NULL,
    option_px       NUMERIC(10,4),
    delta           NUMERIC(6,4),
    premium_paid    NUMERIC(8,4),
    pnl_per_bushel  NUMERIC(8,4),
    net_eff_price   NUMERIC(8,4)
);
SELECT create_hypertable('options_snapshots', 'time');

-- On-farm weather station (Ambient Weather direct)
CREATE TABLE weather_station_local (
    time            TIMESTAMPTZ NOT NULL,
    temp_f          NUMERIC(5,2),
    humidity        NUMERIC(5,2),
    rain_hourly     NUMERIC(6,3),
    rain_daily      NUMERIC(6,3),
    wind_speed      NUMERIC(5,2),
    wind_dir        SMALLINT,
    solar_rad       NUMERIC(7,2),
    baro_rel        NUMERIC(7,3),
    soil_temp_1     NUMERIC(5,2)
);
SELECT create_hypertable('weather_station_local', 'time');

-- Regional weather (Open-Meteo)
CREATE TABLE weather_regional (
    time            TIMESTAMPTZ NOT NULL,
    region          VARCHAR(50) NOT NULL,
    temp_c          NUMERIC(5,2),
    precip_mm       NUMERIC(6,2),
    soil_moisture   NUMERIC(5,3),
    et0             NUMERIC(5,2),
    wind_speed_10m  NUMERIC(5,2)
);
SELECT create_hypertable('weather_regional', 'time');

-- GDU continuous aggregate (auto-updated)
CREATE MATERIALIZED VIEW gdu_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    AVG(temp_f) AS avg_temp_f,
    GREATEST(((MIN(temp_f) + MAX(temp_f)) / 2.0) - 50, 0) AS gdu
FROM weather_station_local
GROUP BY day;
```

### 6.3 MongoDB Collections

```
positions             Options positions (puts and calls, all phases)
usda_releases         Raw WASDE data and parsed numbers
agent_runs            Every agent execution -- full input + output + prompt version
news_articles         Headlines and sentiment scores
conab_reports         Brazilian crop reports
congressional_trades  Quiver Quantitative disclosures
trade_journal         Day trading entries, exits, P&L, notes
elevator_snapshots    Raw scrape results
prompt_versions       Agent prompt history for tuning and rollback
trading_mode_audit    Every mode change (paper/live) with timestamp
```

**Agent run document -- the retrospective tuning record:**

```json
{
  "_id": "ObjectId",
  "agent": "usda_skeptic",
  "run_timestamp": "ISO8601",
  "prompt_version": "v1.3",
  "model": "claude-sonnet-4-20250514",
  "input_snapshot": {
    "wasde_release_date": "...",
    "usda_corn_stocks_mbu": 1842,
    "private_estimate_mean_mbu": 1798,
    "prior_month_usda_mbu": 1856
  },
  "output": {
    "summary": "string",
    "divergence_flag": true,
    "divergence_magnitude": "significant",
    "positioning_note": "string",
    "confidence": 0.74
  },
  "token_usage": { "input": 1240, "output": 387 },
  "cost_usd": 0.031,
  "actual_outcome": null,
  "outcome_notes": null,
  "operator_rating": null
}
```

**Trading mode audit document:**

```json
{
  "_id": "ObjectId",
  "timestamp": "ISO8601",
  "previous_mode": "paper",
  "new_mode": "live",
  "confirmed_by": "operator",
  "confirmation_phrase": "LIVE TRADING",
  "client_ip": "string",
  "user_agent": "string"
}
```

---

## 7. AI Agent Layer

All agents share `base_agent.py` which handles prompt loading from MongoDB, Claude API calls, run document storage, token cost logging, and structured error handling.

### Agent 1: USDA Skeptic

**Trigger:** Scheduled post-WASDE release (monthly, ~10th) or manual  
**Key principle:** The price move lives in the gap between USDA and private trade expectations -- not in the USDA absolute number. Agent frames all output relative to what the market was pricing in before the release.

**Inputs:** Parsed WASDE numbers, private trade estimate average (StoneX, Allendale), prior month USDA, 3-month revision history  
**Output:** Divergence flag + magnitude, directional bias, positioning note, confidence score

### Agent 2: South America Monitor

**Trigger:** Weekly or on-demand before major position decisions  
**Key principle:** Brazil produces more soybeans than the US. Argentine La Nina crop failures have driven 10-30% ZS rallies historically. This agent's output is especially relevant for Phase 2 call decisions.

**Inputs:** Open-Meteo weather for Mato Grosso, Parana, Pampas (30 days + 14-day forecast), CONAB monthly, Rosario Grain Exchange estimates, USDA SA official estimates for comparison  
**Output:** Crop condition by region, divergence from USDA, commodity-specific flags (ZC vs ZS), recommended position implication

### Agent 3: Weather Analyst

**Trigger:** Daily May-September growing season, weekly otherwise  
**Key principle:** Agent must understand crop phenology. A July heat event at corn R1 (pollination) is catastrophic. The same event at V6 is a setback. Prompt must encode this context explicitly.

**Inputs:** On-farm Ambient station (7 days), Open-Meteo corn belt (30 days + forecast), GDU cumulative vs. historical average, planting date from config, SA regional weather  
**Output:** GDU status, soil moisture stress flag, pollination risk flag (corn R1 July), fill period flag (beans R3-R5 August), local vs. regional divergence, market implication

### Agent 4: News Sentiment Filter

**Trigger:** Daily against last 24 hours of articles  
**Key principle:** Aggressive filtering only. Operator does not want general farm news. Only news that could move July ZC, ZS, or ZW futures.

**Keywords:** corn, soybeans, soy, USDA, China trade, ethanol, Black Sea, grain exports, crop insurance, La Nina, El Nino, Argentina drought, Brazil harvest  
**Output:** 3-5 bullet summary, net sentiment per commodity, China demand flag, geopolitical flag, escalation items

### Agent 5: Positioning Advisor

**Trigger:** On-demand or automatically after agents 1-4 complete  
**Key principle:** This agent synthesizes everything and speaks directly to the operator's current position. Its output should be immediately actionable.

**Inputs:** Current positions from MongoDB, latest net effective price, most recent outputs from agents 1-4, days to expiration, operator-defined phase transition rules  
**Output:** Position assessment, specific recommendation (hold/roll/close/adjust), phase transition recommendation, scenario impact snapshot, reasoning summary

---

## 8. Application Modules

### Module 1: Hedge Tracker

**Position entry fields:** commodity, contract month, position type (put/call), strike, premium paid per bushel, number of contracts, delta at entry, expected bushels, phase (1 or 2), date opened, cash sale price (Phase 2)

**Contract size calculator:**
```
Raw contracts = expected bushels / 5000
Delta-adjusted = raw contracts / delta_at_entry
Display both -- flag when materially different
```

**Net effective price calculator:**
```
Phase 1: net = current_cash_price + put_intrinsic_value - total_premiums_paid
Phase 2: net = cash_sale_price_locked + call_pnl - total_premiums_paid (puts + calls)
Always display premium paid as a visible cost line item
```

**Basis tracking:** Store every delivery basis. Display rolling 3-year average by month. Flag when current basis is more than 1 standard deviation from historical average.

**Scenario modeler:** Input a list of hypothetical July futures prices, output net effective price per bushel for each scenario as a formatted table and chart.

**Phase transition alerts:** Operator defines rules in YAML config. Rules are evaluated on a schedule and on position change. Triggered alerts stored in MongoDB and surfaced on dashboard.

### Module 2: Day Trading Sandbox

- Watchlist CRUD with entry target, stop, thesis note, alert threshold
- IPO calendar and recent IPO first-week price action (Finnhub)
- Momentum scanner: volume 2x 20-day average, price move exceeds operator threshold, level breaks
- Alpaca bracket order entry (paper and live mode aware)
- Trade journal: every entry and exit logged with full context including agent state at time of trade

### Module 3: Long-Term Portfolio

- Congressional trade feed from Quiver Quantitative, filtered by operator watchlist
- Position ledger with cost basis, current value, unrealized P&L, days held
- Cross-module overlap alert: congressional disclosure hits a day trading watchlist ticker
- 45-day disclosure lag warning always visible on congressional feed

---

## 9. Frontend UI Design

### Design Language

Dark theme throughout. Color conventions are consistent and semantic:

| Color | Meaning |
|---|---|
| Green | Positive P&L, active/healthy status |
| Red | Negative P&L, live trading mode active |
| Orange/Amber | Agent name accents, alerts, warnings |
| Yellow-green left border | Phase 1 hedge card |
| Blue left border | Phase 2 hedge card |
| Red left border | Live trading active (day trading card) |
| White/light gray | Neutral data, labels |
| Dark gray card bg | `#1a1f2e` or similar -- not pure black |

Cards are the primary layout unit on the main dashboard. Each card is self-contained, shows the most important number prominently, and links to a detail page.

### Main Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  🌽 CORN HEDGE -- JULY ZC                              [PHASE 1]   │
│  BUSHELS          PUTS HELD       NET EFF PRICE        STATUS      │
│  45,000           9 contracts     $4.18 / bu           ACTIVE      │
│                                                                     │
│  OPTIONS P&L (net of premium)               +$0.22/bu  (+$9,900)  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  🌱 SOYBEAN HEDGE -- JULY ZS                           [PHASE 2]   │
│  BUSHELS          CALLS HELD      CASH LOCKED           STATUS     │
│  18,000           4 contracts     $11.42 / bu           ACTIVE     │
│                                                                     │
│  NET EFFECTIVE PRICE                                  $11.67 / bu  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  🌾 WHEAT -- ZW                             Last: $5.42  +0.08     │
│  Wheat as leading indicator -- no position                         │
│  ZW trending: ↑ Bullish signal for grain complex                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  🤖 POSITIONING ADVISOR                      Last run: 6h ago      │
│  CORN:  Hold puts -- USDA divergence bearish, SA crop ok           │
│  BEANS: Monitor -- Brazil harvest 2wks ahead of schedule           │
│  CONFIDENCE: 0.71                  ⚠️  WASDE in 8 days             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐  ┌──────────────────────────────────────┐
│  📈 DAY TRADING          │  │  🏛️  CONGRESSIONAL SIGNALS           │
│  MODE:  ● PAPER          │  │  NVDA -- Pelosi (Buy)  3 days ago    │
│  Today P&L:  +$142       │  │  ⚡ Also in your watchlist           │
│  Open positions:  2      │  │                                      │
│                          │  │  + 2 more disclosures today          │
│  [Go Live ▶]             │  │  (45-day lag -- trailing signal)     │
└──────────────────────────┘  └──────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  🌤  WEATHER                                On-farm + Corn Belt    │
│  Local: 61°F  Rain 7-day: 1.2"  GDU: 847 (12 ahead of avg)        │
│  Corn Belt: Soil moisture adequate  No stress flags                 │
│  SA: Mato Grosso -- Dry pattern developing  ⚠️  Monitor            │
└─────────────────────────────────────────────────────────────────────┘
```

### Price Charts (TradingView Lightweight Charts)

Used on the Hedge detail page and as expandable chart panels. Displays:
- ZC/ZS/ZW candlestick (15-min delayed)
- Basis line overlay (cash minus futures)
- 3-year average basis overlay
- Net effective price horizontal line (current position)
- Strike price horizontal line(s)

TradingView Lightweight Charts is free and open source. It is what professional trading platforms use for web chart rendering. Do not substitute a generic charting library.

### Trade History / Journal Page

Filterable table with expandable rows:

```
Filters: [Date Range] [Commodity/Ticker] [Type] [Win/Loss] [Paper/Live] [Search]

▼ Apr 18   ZC Jul Put $4.20    Phase 1    +$0.18/bu    LIVE
    Entry underlying: $4.31 | Premium paid: $0.14/bu | Exit underlying: $4.13
    Contracts: 9 | Total P&L: +$8,100
    Agent context at entry: "USDA Skeptic flagged bearish divergence, 
    confidence 0.74. SA Monitor neutral."
    Notes: "Held through WASDE, exited day after release. Clean trade."

  Apr 15   NVDA               Long       +$312        PAPER
    Entry: $847 | Exit: $860 | 24 shares | Held: 6h
    Setup: Congressional signal + momentum scan (volume 2.4x avg)
    Notes: "Would have been real. Good read on the setup."
```

### Agent History / Retrospective Page

Lists all agent runs with inputs, outputs, and annotation controls:

```
[Agent ▼] [Date Range ▼] [Rated / Unrated ▼]

USDA Skeptic  --  Jan 10  --  v1.3  --  ⚠️ Divergence: Significant Bearish
  USDA: 1,842M bu  |  Trade mean: 1,798M bu  |  Gap: -44M bu
  Output: "Bearish surprise likely. Market priced for 1,798. 
  USDA coming in 44M above could pressure ZC near-term."
  
  Actual outcome: [_______________]  Rating: ★★★★☆  [Save annotation]
```

### Live Mode Toggle -- Full Specification

This is the highest-risk UI element. Implementation requirements:

1. Default state is always PAPER. Green indicator dot. Day trading card has green left border.
2. "Go Live" button opens a full-screen modal overlay -- not a browser `confirm()` dialog.
3. Modal displays: "You are switching to LIVE trading. Real money is at risk. To confirm, type LIVE TRADING below."
4. Confirm button is disabled until the exact phrase "LIVE TRADING" is typed. Paste should be blocked.
5. On confirm: POST to `/api/trading/mode` with body `{mode: "live"}`. Server validates and writes to MongoDB audit log with client IP, timestamp, and confirmation phrase.
6. Server responds with new mode state. Client reads mode from server response -- never from local state.
7. On live mode active: red left border on day trading card. Site-wide header banner appears: "⚠️ LIVE TRADING ACTIVE -- Real money at risk." Banner is not dismissable while live mode is active.
8. Every order entry form shows current mode prominently before submit.
9. Browser refresh re-fetches mode from server. No stale client state possible.
10. Switching back to paper requires the same modal confirmation with phrase "BACK TO PAPER".

```typescript
// Key principle: server owns mode state
// GET /api/trading/mode --> { mode: "paper" | "live" }
// POST /api/trading/mode --> { mode: "live", confirmed_phrase: "LIVE TRADING" }
// Client never infers mode from local storage or cookies
```

### Real-Time Price Updates (WebSocket)

FastAPI exposes `/ws/prices`. When the yfinance feed writes a new price to TimescaleDB, it broadcasts to all connected WebSocket clients. Next.js dashboard updates immediately. No polling.

```typescript
// hooks/useFuturesPrices.ts
// Connects to ws://api.farm.local/ws/prices
// Reconnects automatically on disconnect
// Updates ZC, ZS, ZW price cards in real time
// Shows stale indicator if no update received in 60 seconds
```

---

## 10. Milestones & Task Checklist

Work through milestones in order. Each milestone should be fully working before starting the next. Commit at every checked task.

---

### MILESTONE 0 -- Infrastructure Setup
**Goal:** VM running, Docker up, all containers healthy, hostnames resolving, Nginx routing working.

#### Proxmox VM
- [ ] Create Ubuntu 24.04 LTS VM (4 vCPU / 8GB RAM / 100GB thin)
- [ ] Assign static LAN IP via UniFi DHCP reservation (tie to VM MAC)
- [ ] Install Docker and Docker Compose on Ubuntu
- [ ] Verify Docker daemon starts on boot (`systemctl enable docker`)

#### Repository
- [x] Initialize git repo, add `.gitignore` (include `.env`, `data/`, `node_modules/`, `__pycache__/`)
- [x] Create `pyproject.toml` with all Python dependencies
- [x] Create `.env.example` with all required keys and comments
- [ ] Create `.env` with real values (never commit this)

#### Docker Compose -- Base Services
- [x] Write `docker-compose.yml` with all services (see Section 10 template below)
- [ ] TimescaleDB container starts and is reachable on internal Docker network
- [ ] MongoDB container starts and is reachable on internal Docker network

#### Nginx Proxy Manager
- [ ] NPM container starts and admin UI is reachable at VM-IP:81
- [ ] Configure proxy host: `farm.local` --> `nextjs:3000`
- [ ] Configure proxy host: `api.farm.local` --> `fastapi:8000`
- [ ] Configure proxy host: `npm.farm.local` --> NPM admin :81

#### UniFi DNS
- [ ] Add local DNS record: `farm.local` --> VM LAN IP
- [ ] Add local DNS record: `api.farm.local` --> VM LAN IP
- [ ] Add local DNS record: `npm.farm.local` --> VM LAN IP
- [ ] Verify `farm.local` resolves from a phone on the LAN
- [ ] Verify `farm.local` resolves from a phone on VPN (outside LAN)

#### Database Init
- [x] Run `scripts/init_db.py` -- creates all hypertables and indexes (script written; run after Docker up)
- [ ] Verify TimescaleDB schema is correct (`\dt` in psql)
- [ ] Verify MongoDB collections exist
- [ ] Run `scripts/backfill_basis.py` -- loads USDA AMS historical basis data
- [ ] Verify basis data is queryable

#### Milestone 0 Acceptance Criteria
- [ ] All containers healthy: `docker compose ps` shows no unhealthy or restarting services
- [ ] `farm.local` loads (Next.js placeholder) from phone on VPN
- [ ] `api.farm.local/docs` loads FastAPI OpenAPI docs

---

### MILESTONE 1 -- Core Data Feeds + Hedge Tracker Backend
**Goal:** Real-time futures prices, local cash/basis, and fully functional hedge tracker with net effective price calculation. No UI yet -- FastAPI endpoints only.

#### Futures Feed
- [x] Implement `farm_platform/feeds/futures_feed.py` (yfinance ZC=F, ZS=F, ZW=F)
- [x] Pull on configurable interval (default 15 min during market hours)
- [x] Write to `futures_prices` hypertable
- [x] Set `stale=True` flag if pull fails -- use last known price, do not crash
- [x] APScheduler job wired up and running
- [ ] Unit test: verify prices landing in TimescaleDB with correct schema

#### Elevator Scraper
- [x] Port operator's existing scraper into `farm_platform/feeds/elevator_scraper.py`
- [x] Standardize output: elevator, commodity, cash_price, futures_ref, basis, contract_month
- [x] Write to `cash_prices` hypertable
- [x] Write raw result to MongoDB `elevator_snapshots`
- [x] Unit test: verify basis calculation (cash minus futures) is correct

#### Hedge Tracker Backend
- [x] Define MongoDB `positions` collection schema (see Section 6.3)
- [x] Implement `farm_platform/hedge/tracker.py` -- CRUD for positions
- [x] Implement `farm_platform/hedge/calculator.py` -- net effective price (Phase 1 and 2)
- [x] Implement delta-adjusted contract count calculator
- [x] Premium always visible as a deduction -- never hidden from net price
- [x] Implement `farm_platform/hedge/scenario_model.py` -- returns table of prices vs. net effective price
- [x] Unit test all calculator functions with known inputs and verified expected outputs

#### FastAPI -- Hedge Routes
- [x] `GET /api/hedge/positions` -- list all positions
- [x] `POST /api/hedge/positions` -- create new position
- [x] `GET /api/hedge/positions/{id}` -- position detail + current P&L
- [x] `PUT /api/hedge/positions/{id}` -- update position (e.g., add cash sale price at Phase 2)
- [x] `GET /api/hedge/net-price` -- current net effective price across all positions
- [x] `POST /api/hedge/scenario` -- run scenario model for a list of hypothetical prices
- [x] `GET /api/prices/futures` -- latest ZC/ZS/ZW prices
- [x] `GET /api/prices/cash` -- latest elevator cash price and basis
- [x] WebSocket `/ws/prices` -- broadcast new prices to connected clients

#### Milestone 1 Acceptance Criteria
- [ ] Futures prices updating on schedule and visible in TimescaleDB
- [ ] Elevator cash price and basis stored and historically accurate
- [ ] POST a test put position, GET back correct net effective price
- [ ] Scenario model returns correct net prices for 5 hypothetical futures prices
- [ ] WebSocket broadcasts a price update within 30 seconds of a new yfinance pull
- [ ] All endpoints return correct responses via FastAPI docs UI

---

### MILESTONE 2 -- Frontend Core + Hedge UI
**Goal:** Next.js dashboard is live at `farm.local`, showing real data, with hedge card and scenario modeler fully functional on mobile and desktop.

#### Next.js Project Setup
- [x] Initialize Next.js 15 project with TypeScript and Tailwind CSS (Next.js 16 / Tailwind v4 -- no tailwind.config.ts, CSS @theme inline)
- [x] Configure dark theme in `tailwind.config.ts` (color tokens, font) -- done via globals.css @theme inline
- [x] Implement `app/layout.tsx` -- dark shell, top navigation, live mode banner placeholder
- [x] Implement typed API client in `lib/api.ts` pointing to `api.farm.local`
- [x] Define TypeScript types in `lib/types.ts` matching FastAPI Pydantic models
- [x] Implement `hooks/useFuturesPrices.ts` WebSocket hook with auto-reconnect and stale indicator

#### Main Dashboard
- [x] Implement `app/page.tsx` -- responsive card grid
- [x] Implement `HedgeCard.tsx` -- Phase 1 (yellow-green border) and Phase 2 (blue border) variants
- [x] Hedge card shows: commodity, contract, bushels, contracts, net effective price, P&L, premium cost
- [x] Prices on hedge card update in real time via WebSocket
- [x] Implement `WeatherCard.tsx` -- placeholder (real data in Milestone 3)
- [x] Implement `AgentCard.tsx` -- placeholder (real data in Milestone 4)
- [x] Implement `DayTradingCard.tsx` -- placeholder with Paper badge, "Go Live" button disabled
- [x] Implement `CongressionalCard.tsx` -- placeholder

#### Hedge Detail Page
- [x] Implement `app/hedge/page.tsx` -- position list with expand/collapse
- [x] Implement `PriceChart.tsx` using TradingView Lightweight Charts
- [x] Chart shows ZC or ZS candlestick + basis overlay + strike price line + net effective price line
- [x] Implement scenario modeler UI -- slider input for price range, output table and line chart
- [x] Implement position entry form (`PositionEntry.tsx`) -- all fields, delta-adjusted count calculated live as operator types
- [ ] Mobile layout verified: all elements usable on a phone screen (verify after Docker up)

#### In-App Analytics Page (replaces Grafana -- see Milestone 2B)
- [ ] Milestone 2B tasks tracked separately below -- Milestone 2 acceptance does not depend on them

#### Milestone 2 Acceptance Criteria
- [x] `farm.local` loads on phone over VPN and shows live hedge card with real prices
- [x] Hedge card prices update without page refresh
- [x] Position entry form calculates delta-adjusted contract count correctly
- [x] Scenario modeler returns correct table when given 5 hypothetical futures prices
- [x] TradingView chart renders ZC candlestick with basis overlay

---

---

### MILESTONE 2B -- In-App Analytics Dashboards
**Goal:** Replace what Grafana was planned to provide — historical charts for futures prices, basis trends, net effective price over time, and eventually weather and agent metrics — all embedded in the Next.js app with no separate login or subdomain. TradingView Lightweight Charts is already integrated; this milestone extends it to historical/analytical views.

**Decision rationale:** Grafana was sunsetted (2026-04-28) because it required a separate login, a separate subdomain, complex provisioning, and a full extra container — all for what amounts to a few time-series charts that TradingView already handles better in-app. Alerting is handled by Python workers (Milestone 4.5), not Grafana alerting.

#### Analytics Page (`/analytics`)
- [ ] Create `app/analytics/page.tsx` — tabbed or sectioned layout, server component
- [ ] Section: **Futures Prices** — ZC/ZS/ZW close price history (TradingView time series, configurable lookback 30/90/365 days)
- [ ] Section: **Basis History** — cash price vs. futures ref, basis line, 3-year average basis overlay; per elevator selector
- [ ] Section: **Net Effective Price** — net effective price per bushel over the crop year, with premium cost visible as a deduction layer
- [ ] Add link to `/analytics` from the `/hedge` page and main nav

#### Weather Charts (add after Milestone 3 data exists)
- [ ] Section: **On-Farm Weather** — temp, rain, GDU cumulative vs. historical average (line chart)
- [ ] Section: **Corn Belt Regional** — soil moisture, precipitation anomaly
- [ ] Section: **South America** — Mato Grosso and Pampas precip and soil moisture trends

#### Agent Metrics (add after Milestone 4 data exists)
- [ ] Section: **Agent History** — confidence scores over time, token cost per agent per month
- [ ] Section: **Positioning Accuracy** — annotated runs with actual vs. predicted outcome overlay

#### Backend additions needed
- [ ] `GET /api/analytics/futures-history?symbol=ZC=F&days=365` — OHLCV array for charting
- [ ] `GET /api/analytics/basis-history?elevator=Toulon&days=180` — basis series
- [ ] `GET /api/analytics/nep-history?days=365` — net effective price series (requires joining positions + options_snapshots)

#### Milestone 2B Acceptance Criteria
- [ ] `/analytics` loads with at least Futures Prices and Basis History charts showing real data
- [ ] Charts are interactive (zoom/pan), mobile-usable
- [ ] No separate login, no separate subdomain — embedded in the app at `farm.local/analytics`

---

### MILESTONE 3 -- Weather Module ✅ COMPLETE
**Goal:** On-farm station data and regional weather feeding into storage and displayed on dashboard.

#### Ambient Weather Feed
- [x] Implement `farm_platform/feeds/ambient_feed.py`
- [x] REST API pull for current conditions (polling every 5 min via APScheduler)
- [x] Parse outdoor fields only: temp, humidity, rain, wind, solar, barometric pressure, dew point, UV, lightning
- [x] Write to `weather_station_local` hypertable with ON CONFLICT DO NOTHING
- [x] `scripts/backfill_ambient.py` — gap-aware historical backfill (checks MIN(time) before fetching)

#### Open-Meteo Regional Feed
- [x] Implement `farm_platform/feeds/openmeteo_feed.py`
- [x] Regions: corn_belt (41.5N 93.5W), mato_grosso (12.5S 55.5W), parana (23.5S 51.5W), pampas (34.5S 60.5W)
- [x] Fields: temp, precipitation, soil moisture, ET0, wind speed 10m
- [x] Write to `weather_regional` hypertable
- [x] Schedule: every 6 hours
- [x] `scripts/backfill_openmeteo.py` — ERA5 archive backfill (free, no key); gap-aware per region

#### GDU Calculator
- [x] Implement `farm_platform/feeds/gdu_calculator.py`
- [x] Daily GDU from `gdu_daily` continuous aggregate (base 50°F, max/min formula)
- [x] Cumulative GDU from planting date — reads from `planting_dates` DB table first, falls back to config
- [x] `planting_dates` table: per-crop per-year records, full CRUD API + UI in GDU tab
- [x] Store in TimescaleDB continuous aggregate view (`gdu_daily`)

#### FastAPI + Frontend
- [x] `GET /api/weather/local` — on-farm station summary
- [x] `GET /api/weather/local/history` — 7/30-day history
- [x] `GET /api/weather/local/rain-totals` — MTD and YTD rain from stored readings
- [x] `GET /api/weather/regional/{region}` — regional snapshot
- [x] `GET /api/weather/regional-history` — all regions, used for slider and trend charts
- [x] `GET /api/weather/gdu` — GDU status for corn and beans
- [x] `GET/PUT/DELETE /api/weather/planting-dates/{commodity}/{year}` — planting date management
- [x] Updated `WeatherCard.tsx` — live local data, GDU section, SA summary, lightning alert, MTD/YTD rain
- [x] `app/weather/page.tsx` — Local Station (current + 30-day slider + 7-day charts), Regional/SA (date slider + monthly rain table), GDU tab

#### UI Enhancements (same session)
- [x] `AnalyticsLineChart` — legend items clickable to toggle series visibility
- [x] Rain chart — added dashed "7-day Total" cumulative line alongside hourly
- [x] Local station date slider — browse any of the 30 backfilled days
- [x] Regional monthly rain totals table — per-region monthly inches summary

#### Milestone 3 Acceptance Criteria
- [x] Ambient station data polling into TimescaleDB continuously (5-min interval)
- [x] Open-Meteo pulling for all 4 regions on schedule (6-hour interval)
- [x] GDU calculation live; planting dates stored in DB, editable via UI
- [x] Weather card on main dashboard shows live on-farm data
- [x] Full `/weather` detail page with Local, Regional/SA, and GDU tabs

---

### MILESTONE 4 -- AI Agent Layer
**Goal:** All five agents operational, storing outputs to MongoDB, visible in the UI, with annotation capability.

#### Agent Infrastructure
- [ ] Implement `platform/agents/base_agent.py`
  - [ ] Prompt load from MongoDB `prompt_versions` by agent name and version
  - [ ] Claude API call (claude-sonnet-4-20250514, max_tokens=1000)
  - [ ] Run document build and write to `agent_runs` with full input snapshot
  - [ ] Token usage and cost_usd logging
  - [ ] Structured error handling for API errors and rate limits
- [ ] Implement `platform/storage/mongo.py` method: `annotate_agent_run(run_id, outcome, notes, rating)`

#### Individual Agents
- [ ] Implement `platform/feeds/usda_feed.py` -- WASDE fetch and parse
- [ ] Implement and test `platform/agents/usda_skeptic.py` -- test against a known historical WASDE
- [ ] Implement `platform/feeds/conab_feed.py` -- Brazilian crop report fetch
- [ ] Implement and test `platform/agents/sa_monitor.py` -- test against 2022 Argentine drought period
- [ ] Implement and test `platform/agents/weather_analyst.py` -- verify crop stage logic in prompt
- [ ] Implement `platform/feeds/news_feed.py` -- NewsAPI + Finnhub with keyword filter
- [ ] Implement and test `platform/agents/news_filter.py` -- verify irrelevant stories are filtered
- [ ] Implement and test `platform/agents/positioning_advisor.py` -- verify it synthesizes agents 1-4 and produces actionable output

#### Phase Transition Alerts
- [ ] Implement `platform/hedge/alerts.py`
- [ ] Read operator-defined rules from YAML config file
- [ ] Evaluate rules against current position state on schedule
- [ ] Store triggered alerts to MongoDB
- [ ] `GET /api/hedge/alerts` -- list active unacknowledged alerts
- [ ] `POST /api/hedge/alerts/{id}/acknowledge` -- mark acknowledged

#### FastAPI + Frontend
- [ ] `GET /api/agents/runs` -- list recent runs with filters
- [ ] `GET /api/agents/runs/{id}` -- full run detail
- [ ] `POST /api/agents/runs/{id}/annotate` -- save outcome, notes, rating
- [ ] `POST /api/agents/{agent}/run` -- trigger manual run
- [ ] Update `AgentCard.tsx` with real positioning advisor output and confidence
- [ ] Add WASDE countdown to agent card (days until next release)
- [ ] Implement `app/agents/page.tsx` -- full agent history with annotation controls
- [ ] Agent run history / cost charts added to in-app analytics page (Milestone 2B)

#### Milestone 4 Acceptance Criteria
- [ ] All five agents run without error
- [ ] Every run stored in MongoDB with full input snapshot, prompt version, token cost
- [ ] At least one historical test run per agent, annotated with actual market outcome
- [ ] Positioning advisor output visible on main dashboard agent card
- [ ] Phase transition alert fires and appears in UI given a test scenario
- [ ] Agent history page shows runs with working annotation controls

---

---

### MILESTONE 4.5 -- Notifications & Alerting
**Goal:** Python-based alerting worker that evaluates thresholds on a schedule and delivers notifications via both email and Telegram. No extra infrastructure — runs as an APScheduler job inside the existing FastAPI container alongside the futures feed and elevator scraper.

**Decision rationale:** Grafana alerting was dropped with Grafana. Email + Telegram covers both the "check your phone in the combine cab" use case (Telegram push) and the "archivable record" use case (email). Both have free tiers with no monthly cost.

#### Alert Types to Implement
- **Basis alert** — basis crosses operator-defined threshold (e.g., Toulon corn basis worse than -0.45)
- **Phase transition alert** — price crosses a configured trigger relative to strike (e.g., futures within 5% of put strike)
- **Net effective price alert** — NEP rises above a target (time to consider closing Phase 1 / opening Phase 2)
- **Stale price alert** — yfinance feed has been stale for more than N minutes during market hours

#### Backend
- [ ] Create `farm_platform/alerts/notifier.py` — delivery layer; accepts a message string and fires both channels
  - [ ] Email via SMTP (Gmail app password or Mailgun free tier — operator's choice, config in `.env`)
  - [ ] Telegram via Bot API (`POST /sendMessage` to operator's personal bot + chat ID)
  - [ ] Graceful degradation: if one channel fails, log error and attempt the other
- [ ] Create `farm_platform/alerts/alert_worker.py` — APScheduler job (every 15 min)
  - [ ] Evaluate all configured alert rules against current DB state
  - [ ] Deduplicate: do not re-fire an alert that fired within the last cooldown window (e.g., 4 hours)
  - [ ] Store each fired alert to MongoDB `alert_history` collection with: type, rule, value, threshold, channels_sent, timestamp
  - [ ] Mark alert as acknowledged when operator calls the acknowledge endpoint
- [ ] Wire alert worker into `backend/main.py` APScheduler on startup
- [ ] Add new `.env` keys: `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_SMTP_HOST`, `ALERT_EMAIL_SMTP_PORT`, `ALERT_EMAIL_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- [ ] Add new config section `AlertSettings` to `farm_platform/config.py`

#### Alert Rules Config
- [ ] Alert thresholds defined in `.env` (simple) or a YAML config file (operator's choice at implementation time)
- [ ] Example `.env` approach: `ALERT_BASIS_CORN_MIN=-0.45`, `ALERT_NEP_CORN_TARGET=4.50`, `ALERT_STALE_MINUTES=30`

#### FastAPI Routes
- [ ] `GET /api/alerts` — list recent fired alerts (last 7 days), with acknowledged status
- [ ] `POST /api/alerts/{id}/acknowledge` — mark acknowledged
- [ ] `GET /api/alerts/config` — current threshold config (read-only, for display in UI)

#### Frontend (light touch — Milestone 4.5 is primarily backend)
- [ ] Alert history panel on main dashboard (unacknowledged alerts only, with acknowledge button)
- [ ] Acknowledge clears alert from dashboard without page reload

#### Milestone 4.5 Acceptance Criteria
- [ ] Basis alert fires and sends both email and Telegram when test threshold is crossed
- [ ] Duplicate suppression working — same alert does not fire twice within cooldown window
- [ ] Alert history visible and acknowledgeable in the UI
- [ ] Both channels deliver within 2 minutes of threshold crossing

---

### MILESTONE 5 -- Day Trading Module
**Goal:** Functional paper trading sandbox visible in UI, with live mode toggle fully implemented.

#### Backend
- [ ] Implement `platform/daytrading/alpaca_client.py`
  - [ ] Mode-aware: reads current mode from MongoDB `trading_mode_audit` -- never from env or client
  - [ ] Paper and live credential sets from `.env` (separate keys)
  - [ ] Bracket order entry, status, cancel
  - [ ] Account equity and P&L query
- [ ] Implement `platform/daytrading/watchlist.py` -- CRUD, price alert storage
- [ ] Implement `platform/daytrading/ipo_tracker.py` -- Finnhub IPO calendar + recent listings
- [ ] Implement `platform/daytrading/momentum_scanner.py` -- volume and price flags on watchlist
- [ ] Implement `platform/daytrading/trade_journal.py` -- log with agent context at time of trade

#### FastAPI Routes
- [ ] `GET /api/trading/mode` -- current mode (paper/live)
- [ ] `POST /api/trading/mode` -- change mode with confirmation phrase validation
- [ ] `GET /api/trading/watchlist` / `POST` / `DELETE /{ticker}`
- [ ] `GET /api/trading/ipo` -- upcoming and recent IPOs
- [ ] `GET /api/trading/momentum` -- scanner results for watchlist
- [ ] `POST /api/trading/orders` -- place bracket order
- [ ] `GET /api/trading/journal` -- trade history with filters
- [ ] `GET /api/trading/account` -- equity, day P&L, open positions

#### Frontend
- [ ] Implement `LiveModeToggle.tsx` per full spec in Section 9
  - [ ] Confirmation modal with typed phrase requirement
  - [ ] Site-wide live mode banner
  - [ ] Red card border in live mode
  - [ ] Mode re-fetched from server on every page load
- [ ] Update `DayTradingCard.tsx` with live account data
- [ ] Implement `OrderEntry.tsx` with mode prominently displayed before submit
- [ ] Implement `app/journal/page.tsx` -- filterable table with expandable rows showing agent context
- [ ] IPO tracker panel in day trading detail page
- [ ] Momentum scanner results panel

#### End-to-End Test
- [ ] Place a paper bracket order via the UI
- [ ] Watch it fill in the Alpaca paper environment
- [ ] Verify it is logged in MongoDB trade journal with correct entry, exit, P&L
- [ ] Verify it appears correctly in the journal page UI

#### Milestone 5 Acceptance Criteria
- [ ] Paper trading working end-to-end including journal logging
- [ ] Live mode toggle requires typed confirmation, writes audit log, shows site-wide banner
- [ ] Mode re-fetched from server on page refresh -- no stale client state
- [ ] Journal page shows all trades with agent context and expandable detail
- [ ] IPO tracker showing upcoming listings

---

### MILESTONE 6 -- Long-Term Portfolio + Congressional Tracker
**Goal:** Congressional feed, portfolio ledger, and cross-module overlap signals.

- [ ] Implement `platform/portfolio/congressional.py` -- Quiver Quantitative API, filter by watchlist
- [ ] Implement `platform/portfolio/ledger.py` -- position tracking, unrealized P&L
- [ ] Implement `platform/portfolio/signal_alerts.py` -- cross-module overlap detection
- [ ] `GET /api/portfolio/congressional` -- recent disclosures filtered by watchlist
- [ ] `GET /api/portfolio/ledger` -- positions with current value and P&L
- [ ] `GET /api/portfolio/signals` -- overlap alerts
- [ ] Update `CongressionalCard.tsx` with real data and 45-day lag warning
- [ ] Implement `app/portfolio/page.tsx` -- full ledger + congressional feed
- [ ] Cross-module overlap alert surfaced on main dashboard when triggered

---

### MILESTONE 7 -- Tuning, Retrospective, and Hardening
**Goal:** Agent feedback loop is working, platform is stable, backups verified.

- [ ] Build retrospective query: agent accuracy rate by prompt version, by market condition type
- [ ] Agent annotation workflow is fast and frictionless in the UI (one-click rating + notes)
- [ ] Prompt version bump workflow: edit in MongoDB, tag in Git, re-run against historical inputs, compare
- [ ] Git tag convention documented: `prompt/usda-skeptic/v1.4` etc.
- [ ] Review all error handling -- every external API call has try/catch, retry logic, and structured log
- [ ] Audit credential handling -- verify nothing appears in application logs or DB records
- [ ] Verify backup cron is running and test restore from backup
- [ ] Container restart policy set to `unless-stopped` for all services
- [ ] Document all operator-configurable parameters in README

---

## 10. Docker Compose

```yaml
version: "3.9"

services:

  nginx-proxy-manager:
    image: jc21/nginx-proxy-manager:latest
    ports:
      - "80:80"
      - "443:443"
      - "81:81"
    volumes:
      - ./data/npm:/data
      - ./data/npm-letsencrypt:/etc/letsencrypt
    restart: unless-stopped

  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: farm_platform
    volumes:
      - ./data/timescale:/var/lib/postgresql/data
    networks:
      - internal
    restart: unless-stopped
    # No host port binding -- internal only

  mongodb:
    image: mongo:7
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    volumes:
      - ./data/mongo:/data/db
    networks:
      - internal
    restart: unless-stopped
    # No host port binding -- internal only

  fastapi:
    build:
      context: .
      dockerfile: backend/Dockerfile
    env_file: .env
    networks:
      - internal
    depends_on:
      - timescaledb
      - mongodb
    restart: unless-stopped

  nextjs:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      NEXT_PUBLIC_API_URL: http://api.farm.local
      NEXT_PUBLIC_WS_URL: ws://api.farm.local
    networks:
      - internal
    depends_on:
      - fastapi
    restart: unless-stopped

networks:
  internal:
    driver: bridge
```

---

## 11. API Credentials Needed

Obtain these before starting Milestone 1. All have free tiers adequate for this use case unless noted.

| Service | URL | Notes |
|---|---|---|
| Anthropic | console.anthropic.com | Claude API -- pay per token, ~$3-8/month projected |
| Ambient Weather | ambientweather.net/account | API key + Application key, free, two separate keys |
| Alpaca | alpaca.markets | Paper trading free, no card needed; live requires account approval |
| NewsAPI | newsapi.org | Free tier: 100 req/day -- sufficient for daily scheduled runs |
| Finnhub | finnhub.io | Free tier: IPO calendar, headlines, basic fundamentals |
| Quiver Quantitative | quiverquant.com | Free tier covers congressional trades |
| Open-Meteo | open-meteo.com | No key required, completely free |
| yfinance | pip install yfinance | No key required |
| USDA AMS | apps.ams.usda.gov | No key required for public grain price data |

---

## 12. Known Constraints & Failure Modes

### Data Quality
- **yfinance is delayed 15 minutes** with no uptime SLA. If a pull fails, write last known price with `stale=True` flag. Surface staleness in the UI -- never show a stale price as if it is current.
- **USDA data is self-reported and lagged.** The USDA Skeptic agent exists because official numbers are an imperfect signal, not ground truth. The August 2020 derecho (Iowa storage bin destruction) is a concrete example of where official storage numbers diverged from physical reality.
- **Basis is hyper-local.** USDA AMS regional averages used for backfill may diverge significantly from the operator's specific elevator. Over time the operator's own scraped data will be more accurate than the backfill.

### Options Mechanics
- **Delta changes continuously.** A put bought at 0.40 delta may be 0.80 delta if the market falls significantly. Delta-adjusted contract counts must be recalculated on every options snapshot, not just at entry.
- **Premium is always a cost.** If puts expire worthless because prices rallied, the premium paid is the cost of having had the floor -- not a trading loss. The platform must always show premium as a deduction from net effective price. Never hide it.
- **Liquidity thins far from the money.** Bid-ask spreads on deep OTM ag options can be wide. Agent recommendations should note when a suggested strike may have execution cost issues.
- **Wheat module is a leading indicator tracker, not a hedging instrument.** ZW is tracked because wheat often prices correlated weather and fund flow before corn and beans. The operator does not grow wheat. Do not show ZW P&L in the hedge tracker.

### AI Agent Limitations
- Agents do not inherently understand farming phenology. The Weather Analyst prompt must explicitly encode crop stage context (V6 vs. R1 corn, R3-R5 beans) or the agent cannot correctly interpret heat or drought signals.
- Confidence scores are self-reported by the model and are not calibrated probabilities. Treat them as relative signals. The annotation and retrospective process in Milestone 7 is what calibrates them over time.
- Projected token cost is $3-8/month at daily agent run frequency. Monitor actual costs during Milestone 4 and adjust run frequency if needed.

### Congressional Trade Module
- Legal disclosure lag is up to 45 days. This is a trailing confirmation signal, not a leading one. The 45-day lag warning must always be visible on the congressional feed. Do not treat disclosures as immediately actionable.

### Security
- Alpaca paper keys have no real-money exposure but must be treated as sensitive to build correct habits before live trading.
- TimescaleDB and MongoDB must not be reachable outside the Docker internal network. Verify with `docker inspect` that no ports are bound to the host interface for these containers.
- All `.env` files must be in `.gitignore`. Verify with `git status` before every commit that no credentials are staged.

---

## 13. Future Expansion

Out of scope for initial build but the architecture supports these without major rework:

- **Push alerts** -- planned in Milestone 4.5 via email (SMTP) + Telegram Bot API. No additional infrastructure required.
- **NDVI satellite data** -- NASA POWER API for crop stress signals before they appear in news or USDA data. Free and REST-accessible.
- **Options chain research** -- Barchart free web tier scrape for researching strikes before entering positions. Complements yfinance which has limited options chain data for futures.
- **Revenue Protection crop insurance integration** -- Track the RP guarantee price alongside options positions to avoid double-counting downside protection.
- **Multi-elevator basis tracking** -- Extend `cash_prices` schema with a second elevator if the operator ever shops between co-ops.
- **Mobile app** -- The Next.js PWA (Progressive Web App) configuration can make `farm.local` installable on iPhone/Android home screen with offline support. No App Store required.
- **Historical agent replay** -- Re-run a new prompt version against stored historical inputs to compare outputs before deploying. The input snapshots stored in MongoDB are what make this possible.

---

*This document is the authoritative build brief for all Claude Code sessions. When starting a new session, provide the relevant milestone section plus Sections 3-6 as context. When a significant architectural deviation is required during development, note it here with rationale before proceeding. Version this document in Git alongside the code.*