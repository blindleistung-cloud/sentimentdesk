# SentimentDesk (v1)

**Server-first, offline-capable (internal), LLM-free market sentiment framework**

> **Decision**: Version 1 is explicitly **without LLMs**. Extraction and scoring are deterministic, traceable, and validated.

---

## 1. Purpose

SentimentDesk ingests weekly market reports with an explicit calendar week (one report per week), extracts the 5-stock focus list (Layer A), and lets you promote those names into a global watchlist. From that decision point, provider data (PE/PB/PCF, trailing-12-month capex, weekly closes) is captured and weekly commentary + mentions are aggregated per stock. The goal is to detect **per-stock trend shifts over rolling 4+ week windows** and surface them in the dashboard.

Key design goals:

* **Objectivity**: metrics-, rules-, and count-based sentiment; no “tone” guessing
* **Traceability**: every score can be explained back to rules and fields (rule trace)
* **Consistency**: explicit calendar week selection; one report per week unless overwrite is confirmed
* **Watchlist-driven**: focus list is the weekly candidate pool; user promotes names to a global watchlist
* **Trend-first**: per-stock signals (weekly closes + PE/PB/PCF + trailing-12-month capex trend)
* **API-efficient**: centralized provider access with **hard caching**, dedupe, and rate-limit awareness
* **Internal-only**: runs on a Raspberry Pi OS–optimized Debian distribution, reachable **only inside the network**
* **Composable**: layer weights and layer fields are configurable in settings

Non-goals:

* no trading signals
* no social media / crowd sentiment ingestion
* no LLM-based extraction in v1

---

## 2. High-level Architecture (Docker)

### Services (Docker Compose)

* **app**: Web backend + Web UI (internal)
* **db**: PostgreSQL (single source of truth)
* **redis**: cache + queue + rate-limit counters
* **worker**: executes provider fetch jobs, parsing jobs, scoring, exports
* **scheduler**: triggers weekly runs, refresh windows, and background maintenance

### Data flow

1. User selects the calendar week and imports/pastes the weekly report (Markdown/Text)
2. API enforces one report per week; overwrite requires explicit confirmation
3. Parser extracts the 5-stock focus list (Layer A) plus capex/risk context (Layers B/C)
4. User promotes focus stocks into a global watchlist
5. Worker fetches provider fundamentals (PE/PB/PCF + trailing-12-month capex), weekly candles for true weekly closes, and index quotes for Layer D
6. Normalizer maps provider outputs into a unified internal schema
7. Validator enforces types/ranges/missing-field rules
8. Scoring engine computes V/C/R and composite sentiment
9. Results stored with full provenance (raw text + extracted schema + report-stock mapping + snapshot refs)
10. UI renders the watchlist dashboard with per-stock drill-downs and aggregated weekly commentary

---

## 3. Tech Stack

### Backend

* Python 3.14
* FastAPI (REST)
* Pydantic (schema + validation)
* SQLAlchemy / asyncpg (PostgreSQL)
* Redis (cache + queue + rate-limits)
* Worker/Scheduler: **RQ + APScheduler** (selected for Raspberry Pi OS / resource efficiency)

### Frontend

* Web UI (internal) built with React + **Tremor** for charts

### Storage

* PostgreSQL: authoritative storage for reports, extracted inputs, scores, snapshots
* Redis: cache for provider responses + job queue + rate counters

---

## 4. Project Structure (target layout)

Target layout (some folders will be added as milestones land):

* `backend/` - API, parsing, providers, jobs
* `frontend/` - internal UI (React + Tremor)
* `infra/` - Docker Compose and env templates
* `docs/` - design decisions and provider docs
* `config/` - settings schema and repo defaults
* `docs/samples/weekly-reports/` - sample weekly report Markdown files for parser/UI testing

## 5. Sentiment Model

### Layers

* **A – Valuation Layer** (scoring; exactly 5 focus stocks that can be promoted to the watchlist)
* **B – Capex Layer** (scoring)
* **C – Risk Narrative Layer** (scoring; count-based clusters)
* **D – Market Context Layer** (non-scoring by default; index moves from provider data)

### Composite score

Default weights (configurable):

```
Sentiment = wV * V + wC * C + wR * R
```

Defaults:

* wV = 0.4
* wC = 0.4
* wR = 0.2

**Important**: weights are user-configurable in Settings.

---

## 6. Configuration (Settings)

Version 1 must allow:

1. **Layer weights** to be adjusted
2. **Layer fields** to be enabled/disabled and refined
3. Provider selection and caching policies to be tuned

### Suggested config surface

* `weights`: { valuation, capex, risk }
* `layers`: per-layer field toggles and defaults
* `providers`: primary, fallback; endpoint toggles
* `caching`: TTL by resource type, hard-cache rules
* `rate_limits`: per provider key and per endpoint policies

A concrete schema (YAML/JSON) will be added in `config/schema.json`.

---

## 7. Providers (2-provider strategy)

### Selection criteria (v1)

* **Free tier / no direct cost** (acceptable: free account + API key)
* Fundamentals and financial statements sufficient to compute **PE/PB/PCF** (or their components)
* Capex or cash-flow line items sufficient for **Capex-related** fields
* Stable documentation and reasonable rate limits

### Chosen providers (v1)

1. **Primary: SimFin (Free account)**

   * Focus: fundamentals/financials (incl. cash-flow and Capex-related items), broad equity coverage
   * Strength: bulk-style usage via Python tooling and local disk caching patterns

2. **Fallback: Finnhub (Free plan)**

   * Focus: company profile + supplemental fundamentals and quotes where needed
   * Strength: generous per-minute rate limits on the free plan (personal-use terms apply)

Notes:

* Provider usage is centralized and normalized into an internal `MarketDataSnapshot` model.
* If SimFin lacks a symbol/field or is temporarily unavailable, Finnhub is used as fallback.

## 8. Hard Caching Policy

Goal: **minimize API calls** and respect free-tier limits.

### Cache principles

* Cache key includes: provider + endpoint + symbol + period + params
* Dedupe: identical request across week runs executes once
* Use **stale-while-revalidate** where appropriate (internal-only UI)

### TTL guidance (initial)

* Company profile: 30 days
* Fundamentals/financials (quarterly): 7–30 days
* Capex series: 30 days
* Prices (if used): 1 day

### “Hard cache” mode

In hard-cache mode, the system:

* prefers cached responses within TTL
* avoids optional refreshes unless explicitly triggered
* tracks daily API budget and refuses non-critical fetches if exceeded

---

## 9. Database Model (core tables)

### `weekly_reports`

* `week_id` (unique, e.g., 2026-W03)
* `raw_text`
* `extracted_inputs_json` (A–D)
* `validation_status` + `validation_issues_json`
* `valuation_score` / `capex_score` / `risk_score` / `composite_score`
* `rule_trace_json`
* `created_at`

### `report_stocks`

* `report_id`
* `ticker` / `name` / `rank`
* `focus_commentary`
* `mention_snippets_json`
* `pe_ratio` / `pb_ratio` / `pcf_ratio`
* `created_at`

### `watchlist_items`

* `ticker` / `name`
* `active`
* `added_at` / `removed_at`

### `market_data_snapshots`

* `snapshot_id`
* `provider`
* `symbol`
* `as_of_date`
* `payload_json`
* `cache_key`
* `status`
* `created_at`

---

## 10. Internal-only Deployment (Raspberry Pi OS / Debian)

### Assumptions

* App reachable only via LAN/VPN (no public exposure)
* Reverse proxy optional (Caddy/Nginx) for TLS even internally

### Security baseline

* Strong auth (username/password, session-based)
* Secrets managed via environment variables or Docker secrets
* DB backups (nightly) to local NAS/share

---

## 11. Development Roadmap (v1)

### Milestone 1 — Core pipeline (done)

* [x] Schema A–D input form (parser + manual entry)
* [x] Validation + rule trace (warn/fail + persisted)
* [x] Score calculation
* [x] Persistence in PostgreSQL
* [x] One report per calendar week (explicit week confirmation + overwrite guard)
* [x] Report-stock mapping (focus commentary + mentions)
* [x] Global watchlist endpoints

### Milestone 2 — Provider integration + caching

* Primary provider adapter
* Fallback provider adapter
* Normalizer to `MarketDataSnapshot`
* Redis caching + TTL policies
* Weekly closes (Finnhub candles) for watchlist stocks

### Milestone 3 — Worker/Scheduler

* Weekly scheduled run
* On-demand refresh
* Rate-limit handling and budgets

### Milestone 4 — Trend dashboards

* Per-stock 4+ week trend charts (PE/PB/PCF + capex trend)
* Per-stock drill-down with aggregated weekly commentary + weekly closes
* Settings area to adjust inputs, add reports and watchlist entries, focus deep-dive for a watchlist stock, and a macroeconomic tab for sentiment shifts
* Trend delta highlights and ranking
* Alerts view (threshold-based)

---

## 12. License & Disclaimer

SentimentDesk is a decision-support tool. It does not provide financial advice or trading recommendations.

---

## 13. Quick Start

1. Read `AGENTS.md` for workflows, constraints, and commands.
2. Keep your weekly report Markdown samples handy (recommended: `docs/samples/weekly-reports/`) to test parsing and input flow.
3. In the UI, select the report week (YYYY-Www) and confirm it before parsing; enable overwrite only to replace an existing week.
4. If `uv` cache initialization fails due to permissions, set `UV_CACHE_DIR` to a writable folder before running `uv` commands (create the folder if needed). Examples:
```
$env:UV_CACHE_DIR = "$PWD\\.uv-cache"
```
```
export UV_CACHE_DIR="$PWD/.uv-cache"
```
5. When `infra/docker-compose.yml` is present, run:

```
docker compose -f infra/docker-compose.yml up --build
```

---

## 14. Next documents

* `AGENTS.md` (system behavior, parsing rules, validation, caching, job orchestration)
* `config/schema.json` (settings schema)
* `docs/provider-adapters.md` (provider endpoints and normalization)

