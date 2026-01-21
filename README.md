# SentimentDesk (v1)

**Server-first, offline-capable (internal), LLM-free market sentiment framework**

> **Decision**: Version 1 is explicitly **without LLMs**. Extraction and scoring are deterministic, traceable, and validated.

---

## 1. Purpose

SentimentDesk transforms weekly market reports into a **structured input schema** (Layers A–D) and computes a **reproducible composite sentiment score**.

Key design goals:

* **Objectivity**: metrics-, rules-, and count-based sentiment; no “tone” guessing
* **Traceability**: every score can be explained back to rules and fields (rule trace)
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

1. User imports/pastes weekly report (Markdown/Text)
2. Parser extracts candidate fields (A–D) and risk-cluster counts (C)
3. Worker fetches missing fundamentals/capex data via **2 providers** (primary + fallback)
4. Normalizer maps provider outputs into a unified internal schema
5. Validator enforces types/ranges/missing-field rules
6. Scoring engine computes V/C/R and composite sentiment
7. Results stored with full provenance (raw text + extracted schema + snapshot refs)
8. UI renders dashboards and charts via **Tremor**

---

## 3. Tech Stack

### Backend

* Python 3.12
* FastAPI (REST)
* Pydantic (schema + validation)
* SQLAlchemy / asyncpg (PostgreSQL)
* Redis (cache + queue + rate-limits)
* Worker/Scheduler: Celery (Redis broker) or RQ + APScheduler (final choice documented in `docs/decisions/`)

### Frontend

* Web UI (internal) built with React + **Tremor** for charts

### Storage

* PostgreSQL: authoritative storage for reports, extracted inputs, scores, snapshots
* Redis: cache for provider responses + job queue + rate counters

---

## 4. Sentiment Model

### Layers

* **A – Valuation Layer** (scoring)
* **B – Capex Layer** (scoring)
* **C – Risk Narrative Layer** (scoring; count-based clusters)
* **D – Market Context Layer** (non-scoring by default)

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

## 5. Configuration (Settings)

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

## 6. Providers (2-provider strategy)

### Provider requirements

* Fundamentals: KGV/KBV/KCV or components to compute them
* Financials: revenue, earnings, operating cashflow
* Capex: capex series or capex-related fields
* Company metadata: ticker mapping, market cap (if available)

### Provider strategy

* **Primary provider**: default data source
* **Fallback provider**: used if primary misses symbols/fields or rate-limits

All provider outputs are normalized into an internal schema (`MarketDataSnapshot`).

---

## 7. Hard Caching Policy

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

## 8. Database Model (core tables)

### `weekly_reports`

* `week_id` (e.g., 2026-W03)
* `date_range`
* `raw_text`
* `extracted_inputs_json` (A–D)
* `validation_status`
* `created_at`

### `market_data_snapshots`

* `snapshot_id`
* `provider`
* `symbol`
* `as_of_date`
* `payload_json`
* `cache_key`
* `created_at`

### `scores`

* `week_id`
* `valuation_score`
* `capex_score`
* `risk_score`
* `composite_score`
* `rule_trace_json`

---

## 9. Internal-only Deployment (Raspberry Pi OS / Debian)

### Assumptions

* App reachable only via LAN/VPN (no public exposure)
* Reverse proxy optional (Caddy/Nginx) for TLS even internally

### Security baseline

* Strong auth (username/password, session-based)
* Secrets managed via environment variables or Docker secrets
* DB backups (nightly) to local NAS/share

---

## 10. Development Roadmap (v1)

### Milestone 1 — Core pipeline

* Schema A–D input form
* Validation + rule trace
* Score calculation
* Persistence in PostgreSQL

### Milestone 2 — Provider integration + caching

* Primary provider adapter
* Fallback provider adapter
* Normalizer to `MarketDataSnapshot`
* Redis caching + TTL policies

### Milestone 3 — Worker/Scheduler

* Weekly scheduled run
* On-demand refresh
* Rate-limit handling and budgets

### Milestone 4 — Tremor dashboards

* Composite time series
* Layer breakdown charts
* Alerts view (threshold-based)

---

## 11. License & Disclaimer

SentimentDesk is a decision-support tool. It does not provide financial advice or trading recommendations.
