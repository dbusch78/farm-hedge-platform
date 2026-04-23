# Farm Platform

A personal Python monorepo for farm-focused hedging and speculative trading tools.

## Modules

### 1. CBOT Options Hedge Tracker (`src/cbot_hedge/`)
Tracks corn and soybean options positions on the Chicago Board of Trade (CBOT).
Connects to Interactive Brokers TWS/Gateway via `ib_async` to monitor open hedges
against physical crop exposure, calculate delta/gamma, and surface roll alerts.

### 2. Alpaca Day Trading Sandbox (`src/day_trading/`)
Paper-trading sandbox wired to the Alpaca API. Allows backtesting and live paper
execution of intraday equity strategies without risking real capital.

### 3. Congressional Portfolio Tracker (`src/congress_tracker/`)
Polls public congressional stock disclosure feeds (House and Senate) and tracks
notable trades relative to your own long-term portfolio holdings.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install all extras for local dev
pip install -e ".[all]"

# Copy and fill in secrets
cp .env.example .env
```

## Running tests

```bash
pytest
```

## Project layout

```
src/
  config/           # Shared settings (pydantic-settings, loaded from .env)
  cbot_hedge/       # CBOT options hedge tracker
  day_trading/      # Alpaca paper-trading sandbox
  congress_tracker/ # Congressional disclosure tracker
tests/
  test_cbot_hedge/
  test_day_trading/
  test_congress_tracker/
```
