# Farm Hedge + Day Trading Platform

Personal-use commodity hedging, day trading sandbox, and portfolio tracker.
See `CLAUDE_CODE_BRIEF.md` for full architecture and design decisions.

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Docker + Docker Compose | v25 / v2.24 | Compose v2 (`docker compose`, not `docker-compose`) |
| Python | 3.12 | Backend dev / scripts only |
| Node.js | 24 | Frontend dev only |
| Chrome / Chromium | any recent | Required by elevator scraper (Selenium) |

---

## Deployment Environments

This project has two target environments. The setup steps differ only in how DNS is resolved.

| | WSL / Windows (dev + initial testing) | Ubuntu VM (production) |
|-|---------------------------------------|------------------------|
| Docker runs in | WSL2 on your Windows 11 PC | Native Docker on Proxmox VM |
| Hostnames resolve via | Windows `hosts` file (`C:\Windows\System32\drivers\etc\hosts`) | UniFi Dream Machine DNS overrides |
| All hostnames point to | `127.0.0.1` | VM's LAN IP |
| NPM admin | `http://localhost:81` | `http://<vm-ip>:81` |

Everything else — Docker commands, database init, NPM proxy config, acceptance tests — is identical between the two environments.

---

## First-Time Setup

### 1. Clone and configure environment

```bash
git clone <repo> farm-hedge-platform
cd farm-hedge-platform

cp .env.example .env
# Edit .env -- fill in passwords and any API keys you have now.
# At minimum set POSTGRES_PASSWORD, MONGO_PASSWORD, and GRAFANA_PASSWORD.
# Leave optional keys (Alpaca, Ambient, etc.) blank until those milestones.
```

Key `.env` values to set before first boot:

| Variable | What to set |
|----------|-------------|
| `POSTGRES_PASSWORD` | Any strong password |
| `POSTGRES_DSN` | Update password to match above |
| `MONGO_PASSWORD` | Any strong password |
| `MONGO_URI` | Update password to match above |
| `ANTHROPIC_API_KEY` | From console.anthropic.com (needed for Milestone 4) |
| `ELEVATOR_RVC_EMAIL` | Your RVC account email |
| `ELEVATOR_RVC_PASSWORD` | Your RVC account password |
| `ELEVATOR_CASH_BIDS_URL` | Confirm from browser DevTools Network tab logged into RVC site |
| `ELEVATOR_NAMES` | Exact location name(s) from RVC API (e.g. `Toulon`) |

### 2. Build and start all services

```bash
docker compose up -d --build
```

This starts: TimescaleDB, MongoDB, FastAPI backend, Next.js frontend, and Nginx Proxy Manager.

Check that all containers came up healthy:

```bash
docker compose ps
```

All services should show `running`. If any show `restarting`, check logs:

```bash
docker compose logs <service-name>
```

### 3. Initialize the databases

Run once after the first `docker compose up --build`:

```bash
docker compose exec fastapi python scripts/init_db.py
```

This creates:
- TimescaleDB hypertables: `futures_prices`, `cash_prices`, `options_snapshots`, `weather_*`
- MongoDB collections + indexes: `positions`, `agent_runs`, `elevator_snapshots`, `trading_mode_audit`

### 4. Configure DNS

**WSL / Windows (dev)** — edit `C:\Windows\System32\drivers\etc\hosts` as Administrator and add:

```
127.0.0.1  farm.local
127.0.0.1  api.farm.local
127.0.0.1  npm.farm.local
```

**Ubuntu VM (production)** — on your UniFi Dream Machine, add DNS overrides pointing all three `*.farm.local` names to the VM's LAN IP.

### 5. Configure Nginx Proxy Manager

1. Open NPM admin UI:
   - WSL/Windows: `http://localhost:81`
   - Ubuntu VM: `http://<vm-ip>:81`
2. Default login: `admin@example.com` / `changeme` (you will be forced to change it)
3. Add three proxy hosts (forward hostname is always the Docker service name — same in both environments):

| Domain | Forward Hostname | Forward Port |
|--------|-----------------|-------------|
| `farm.local` | `nextjs` | `3000` |
| `api.farm.local` | `fastapi` | `8000` |
| `npm.farm.local` | `nginx-proxy-manager` | `81` |

> **Network topology note:** NPM must be attached to both the `default` and `internal`
> Docker networks. App services (`fastapi`, `nextjs`) live on `internal` only for
> isolation; NPM bridges both so it can receive external traffic on `default` (ports
> 80/443/81) and reach upstreams on `internal`. This is already correct in
> `docker-compose.yml` — do not remove the `networks:` block from the
> `nginx-proxy-manager` service. If NPM shows upstream hosts as "Online" but every
> hostname returns 502, the most likely cause is that NPM lost its `internal` network
> attachment (e.g. after a compose file edit) — recreate it with
> `docker compose up -d nginx-proxy-manager`.

### 6. Seed existing positions (optional)

```bash
docker compose exec fastapi python scripts/seed_positions.py --dry-run
# Review output, then run without --dry-run to insert
docker compose exec fastapi python scripts/seed_positions.py
```

Edit `scripts/seed_positions.py` to fill in your actual position data before running.

---

## Service URLs

| Service | WSL / Windows | Ubuntu VM |
|---------|--------------|-----------|
| Dashboard | http://farm.local | http://farm.local |
| Hedge detail | http://farm.local/hedge | http://farm.local/hedge |
| FastAPI docs | http://api.farm.local/docs | http://api.farm.local/docs |
| NPM admin | http://localhost:81 | http://npm.farm.local |

---

## Local Development (without Docker)

Useful for rapid iteration on backend logic or frontend components without rebuilding images.

### Backend

```bash
python -m venv .venv
source .venv/bin/activate        # WSL / Linux / Mac
# .venv\Scripts\activate         # Windows PowerShell

pip install -e ".[all]"

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The backend reads `.env` for database DSNs. When running outside Docker, `timescaledb` and `mongodb` won't resolve — temporarily change those DSN hostnames to `localhost` in your `.env` and expose the database ports in `docker-compose.yml`:

```yaml
  timescaledb:
    ports:
      - "5432:5432"   # add for local dev only
  mongodb:
    ports:
      - "27017:27017" # add for local dev only
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

`frontend/.env.local` points to `http://localhost:8000`. Make sure the FastAPI backend is running before loading the UI.

---

## Running Tests

### Python unit tests

```bash
# From project root with venv active
pytest

# Verbose
pytest -v

# Single module
pytest tests/platform/test_calculator.py
```

Current coverage: hedge calculator, scenario model (15 tests, all pure-function, no Docker needed).

### Frontend type check + build

```bash
cd frontend
npm run build      # Type-checks and produces a production build -- exit 0 = clean
```

---

## Milestone 2 Acceptance Checklist

Work through these after the Docker stack is up and DNS is resolving. Substitute `localhost` for `farm.local` etc. if testing in WSL before setting up the hosts file.

### Infrastructure
- [x] `docker compose ps` shows all services running, none restarting
- [x] `http://api.farm.local/docs` loads FastAPI OpenAPI UI
- [x] `http://farm.local` loads the dashboard in a browser

### Live prices and WebSocket
- [x] Main dashboard shows ZC and ZS prices on the HedgeCard
- [x] Prices update without a page refresh (WebSocket connected — check DevTools → Network → WS)
- [x] ZW (wheat) leading indicator card shows a price
- [x] Stale indicator appears if the backend is stopped and ~60 seconds elapse

### Hedge card and positions
- [x] HedgeCard shows correct bushels, contracts, premium cost, and net effective price for each open position
- [x] Phase 1 positions have yellow-green border; Phase 2 positions have blue border

### Hedge detail page (`/hedge`)
- [x] ZC and ZS sections each show a TradingView candlestick chart with basis overlay
- [x] Strike price horizontal line and net effective price line visible on chart
- [x] Position list renders under each commodity section
- [x] Scenario modeler: enter a price range and step count, verify the output table rows change
- [x] Highlighted row tracks the current futures price; at-strike row highlighted differently

### Position entry form
- [x] Form at bottom of `/hedge` renders all fields
- [x] Delta-adjusted contract count updates live as you type bushels and delta
- [x] Cash sale price field appears when option type is set to `call` (Phase 2)
- [x] Submitting the form adds a position (verify via `GET /api/hedge/positions` in FastAPI docs)

### Mobile (production environment only)
- [x] Load `farm.local` from a phone on the LAN — all cards readable, no overflow
- [x] Load `farm.local` from a phone on VPN (outside LAN) — same result

---

## Clean Install Verification

After a fresh `docker compose up --build`, run these in order to confirm everything is wired correctly:

```bash
# 1. All five containers running, none restarting
docker compose ps

# 2. Initialize databases (run once only)
docker compose exec fastapi python scripts/init_db.py

# 3. API docs reachable
curl -s http://localhost:8000/docs | grep -q "Farm Platform" && echo "API OK"

# 4. Wait ~60 seconds for the first scheduler tick, then confirm a price landed
docker compose exec timescaledb psql -U farm -d farm_platform \
  -c "SELECT COUNT(*) FROM futures_prices;"
# Expected: count > 0

```

All five containers must stay `running` for at least 2 minutes. `docker compose logs fastapi` must show `Application startup complete` with no traceback.

---

## Daily Operations

```bash
# Start all services
docker compose up -d

# Stop all services (keeps volumes)
docker compose down

# Full teardown including all volumes (destructive -- loses all DB data)
docker compose down -v

# View live logs from a service
docker compose logs -f fastapi

# Restart a single service after a code change
docker compose restart fastapi

# Rebuild after code changes (backend or frontend Dockerfile)
docker compose up -d --build fastapi
docker compose up -d --build nextjs
```

**Note:** Futures prices and elevator cash bids are pulled exclusively by the APScheduler jobs inside the FastAPI container. The API starts and serves requests regardless of feed health — a yfinance timeout or DB hiccup will log an error and retry on the next scheduled tick without taking the API down.

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + uvicorn |
| Task scheduling | APScheduler |
| Time-series DB | TimescaleDB (PostgreSQL 16) |
| Document DB | MongoDB 7 |
| Frontend | Next.js 16 / React 19 / Tailwind v4 |
| Charts | TradingView Lightweight Charts v5 |
| Reverse proxy | Nginx Proxy Manager |
| Market data | yfinance (ZC, ZS, ZW futures) |
| AI agents | Anthropic Claude API (Milestone 4) |
