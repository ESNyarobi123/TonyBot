# 📡 ERICKsky Signal Engine

A production-ready Forex signal generation system that fetches real-time market data, runs 4 sophisticated trading strategies in parallel, applies a consensus algorithm, and delivers high-quality signals via Telegram — all managed through a live Laravel dashboard.

---

## 🏗 Architecture Overview

```
ERICKsky-signal-engine/
├── signal-bot/          # Python 3.11 signal engine
├── dashboard/           # Laravel 12 + Livewire 3 dashboard
├── nginx/               # Reverse proxy configuration
└── docker-compose.yml   # Full stack orchestration
```

### Signal Pipeline

```
Market Data (Twelve Data API)
        ↓
  Redis Cache Layer
        ↓
  ┌─────────────────────────────────────────┐
  │  4 Strategies (Celery parallel tasks)   │
  │  1. Multi-Timeframe (MTF)  — 25%        │
  │  2. Smart Money Concepts   — 30%        │
  │  3. Price Action + S/R     — 25%        │
  │  4. Technical Indicators   — 20%        │
  └─────────────────────────────────────────┘
        ↓
  Consensus Engine (weighted voting)
        ↓
  4 Filters: Session / News / Spread / Volatility
        ↓
  Signal Validator (R:R, price logic checks)
        ↓
  PostgreSQL (persisted)  +  Telegram delivery
        ↓
  Laravel Dashboard (real-time Livewire UI)
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Twelve Data API key (https://twelvedata.com)
- Telegram Bot token (from @BotFather)
- Telegram channel/group chat IDs

### 1. Clone & Configure

```bash
git clone <repo-url> ERICKsky-signal-engine
cd ERICKsky-signal-engine

# Root env (Docker Compose DB password)
cp .env.example .env
# Edit .env and set DB_PASSWORD

# Signal bot env
cp signal-bot/.env.example signal-bot/.env
# Fill in: TWELVE_DATA_API_KEY, TELEGRAM_BOT_TOKEN, DB_PASSWORD, etc.

# Dashboard env
cp dashboard/.env.example dashboard/.env
php artisan key:generate  # or set APP_KEY manually
```

### 2. Start All Services

```bash
docker-compose up -d
```

Services started:
| Container | Role | Port |
|-----------|------|------|
| `erickskybot-engine` | Python signal bot | — |
| `erickskybot-celery` | Celery workers (4 concurrent) | — |
| `erickskybot-beat` | Celery beat scheduler | — |
| `erickskybot-dashboard` | Laravel dashboard | 8000 |
| `erickskybot-postgres` | PostgreSQL 15 | 5432 |
| `erickskybot-redis` | Redis 7 | 6379 |
| `erickskybot-nginx` | Nginx reverse proxy | 80/443 |

### 3. Run Database Migrations

```bash
# Schema is auto-applied from schema.sql on first PostgreSQL start
# For Laravel migrations:
docker-compose exec dashboard php artisan migrate --force
```

### 4. Access Dashboard

Open: `http://localhost` (or your domain via HTTPS)

---

## ⚙️ Configuration

### Key Environment Variables (`signal-bot/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `TWELVE_DATA_API_KEY` | Twelve Data API key | **required** |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | **required** |
| `TELEGRAM_FREE_CHANNEL` | Free channel chat ID | **required** |
| `TELEGRAM_PREMIUM_CHANNEL` | Premium channel chat ID | **required** |
| `TRADING_PAIRS` | Comma-separated pairs | `EURUSD,GBPUSD,USDJPY,XAUUSD` |
| `MIN_CONSENSUS_SCORE` | Minimum score to send signal (0-100) | `75` |
| `SCAN_INTERVAL_MINUTES` | How often to scan pairs | `60` |
| `SIGNAL_VALID_MINUTES` | Signal expiry time | `30` |

### Strategy Weights (must sum to 100)

| Strategy | Weight | Description |
|----------|--------|-------------|
| `STRATEGY_WEIGHT_MULTI_TIMEFRAME` | 25 | 4H/1H/15m alignment |
| `STRATEGY_WEIGHT_SMART_MONEY` | 30 | OB / FVG / BOS / Liquidity |
| `STRATEGY_WEIGHT_PRICE_ACTION` | 25 | Patterns / S&R / Structure |
| `STRATEGY_WEIGHT_TECHNICAL` | 20 | RSI / MACD / BB / EMA |

---

## 📊 Dashboard Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Live feed, charts, stats |
| Signals | `/signals` | Full history with filters + CSV export |
| Subscribers | `/subscribers` | Manage Telegram subscribers |
| Telegram | `/telegram` | Channel config + test messages |
| Performance | `/performance` | Analytics, win rate by pair/hour |

---

## 🔬 Strategies

### 1. Multi-Timeframe (MTF)
- **4H**: EMA 50/200 trend definition + higher highs/lows
- **1H**: EMA 21/50 + RSI confirmation  
- **15min**: EMA 9/21 crossover entry timing

### 2. Smart Money Concepts (SMC)
- **Break of Structure (BOS/CHoCH)**: Identifies trend shifts
- **Order Blocks**: Last opposing candle before impulse
- **Fair Value Gaps (FVG)**: Imbalance zones for re-entry
- **Liquidity Sweeps**: Institutional trap + reversal detection

### 3. Price Action + S/R
- **Candlestick Patterns**: Engulfing, Hammer, Star, Marubozu
- **Support/Resistance**: Swing high/low level reactions
- **Market Structure**: HH/HL vs LH/LL classification
- **Wick Analysis**: Rejection candle detection

### 4. Technical Indicators
- **RSI** (14): Oversold/overbought + divergence
- **MACD** (12/26/9): Crossover + histogram expansion
- **Bollinger Bands** (20, 2σ): Band touch + width
- **EMA Stack** (20/50/200): Trend alignment
- **Stochastic** (14,3): Cross + zone analysis

---

## 🔍 Filters

| Filter | Purpose |
|--------|---------|
| **Session** | London (07-16 UTC) + NY (12-21 UTC) only |
| **News** | Blocks signals ±30min of high-impact events |
| **Spread** | Rejects if spread > max allowed per pair |
| **Volatility** | Requires ATR ≥ minimum pips threshold |

---

## 🗄 Database Schema

See `signal-bot/database/schema.sql` for the full PostgreSQL schema.

Key tables: `signals`, `subscribers`, `pair_performance`, `telegram_channels`, `bot_state`

---

## 🧪 Running Tests

```bash
cd signal-bot
pip install -r requirements.txt
pytest tests/ -v
```

---

## 🐳 Docker Commands

```bash
# View logs
docker-compose logs -f signal-bot
docker-compose logs -f celery-worker

# Restart a service
docker-compose restart signal-bot

# Run manual scan (all pairs)
docker-compose exec celery-worker celery -A celery_app call tasks.scan_all_pairs

# Force scan a specific pair
docker-compose exec celery-worker celery -A celery_app call tasks.scan_pair --args='["EURUSD"]' --kwargs='{"force_session":true}'

# Check Celery status
docker-compose exec celery-worker celery -A celery_app inspect active
```

---

## 📁 Project Structure

```
signal-bot/
├── main.py                    # Entry point + startup checks
├── scheduler.py               # APScheduler setup
├── celery_app.py              # Celery + beat schedule
├── config/settings.py         # All configuration
├── data/
│   ├── twelve_data.py         # Twelve Data SDK wrapper
│   ├── data_fetcher.py        # Cache-aware OHLCV fetcher
│   └── cache_manager.py       # Redis caching layer
├── strategies/
│   ├── base_strategy.py       # Abstract base + shared helpers
│   ├── multi_timeframe.py     # Strategy 1: MTF alignment
│   ├── smart_money.py         # Strategy 2: SMC
│   ├── price_action.py        # Strategy 3: PA + S/R
│   ├── technical.py           # Strategy 4: Indicators
│   └── consensus_engine.py    # Weighted voting
├── filters/                   # session/news/spread/volatility
├── signals/                   # generator/validator/formatter
├── notifications/             # Telegram delivery
├── database/                  # PostgreSQL manager + repos
├── tasks/                     # Celery tasks
├── utils/                     # logger/helpers/constants
└── tests/                     # pytest test suite
```

---

## ⚠️ Disclaimer

This system is for **educational and research purposes only**. Forex and gold trading involves substantial risk. Past performance does not guarantee future results. Always use proper risk management and consult a licensed financial advisor.

---

## 📄 License

MIT License — ERICKsky Signal Engine © 2024
