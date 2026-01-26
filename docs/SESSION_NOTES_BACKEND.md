# Session Notes (Backend)

## Changes
- Align runtime to Python 3.14 in AGENTS.md and backend/pyproject.toml; refreshed backend/uv.lock; dev deps moved to dependency-groups.dev; pytest pythonpath added.
- Added deterministic provider snapshot cache keys (provider:symbol:week_id) and cache_key field wiring; /parse enqueues provider job instead of calling providers.
- Added RQ queue integration and provider fetch job; new job modules; idempotent inserts via cache_key.
- Added Redis snapshot cache with TTLs (success + error); warning logs on cache failure.
- Updated SimFin adapter to v3 endpoint with Authorization header and check_api_key; Finnhub adapter used as fallback.
- Added status column to market_data_snapshots; migrations README includes manual ALTER; verified column exists in running DB.
- Updated backend Dockerfile to run uvicorn via `uv run`.
- Added validation result schema (ok/warn/fail) and manual report endpoint `/api/report/manual` with required tickers.
- Added deterministic validation module (exactly 5 stocks, missing ticker warn/fail, range checks) and persisted validation status/issues to `weekly_reports`.
- Applied ticker overrides before validation/scoring in `/api/parse`; manual endpoint cleans markdown and queues provider fetches.
- Updated migrations README with `weekly_reports` validation columns.
- Updated parse enqueue tests for five-stock rule, validation status, and manual endpoint coverage.
- Added watchlist + report-stock mapping (focus commentary + mentions) and stock history endpoints.
- Fetch weekly Finnhub candles for watchlist stocks to store true weekly closes.
- Require explicit `week_id` for parse/manual endpoints; block duplicate week unless `allow_overwrite` is set.

## Tests
- `uv run pytest backend/tests/test_smoke_imports.py -q`
- `uv run pytest backend/tests/test_provider_cache_key.py -q`
- `uv run pytest backend/tests/test_provider_cache.py -q`
- `uv run pytest backend/tests/test_parse_enqueues_provider_job.py -q` (manual endpoint + validation updates)

## Commits
- `1f7d93b` Align Python 3.14 runtime and add backend smoke test
- `ec151ed` Add snapshot cache keys and uv dev setup
- `2eda92d` Move provider fetch to RQ job
- `941202c` Wire SimFin v3 auth and endpoint
- `48506b0` Add Redis cache for provider snapshots

## Notes / Ops
- uv cache permission errors on Windows; set `UV_CACHE_DIR` to a writable path (e.g. repo `.uv-cache`).
- Docker engine pipe may require Docker Desktop running and a fresh session; use full path to docker.exe if PATH missing.
- SimFin v3 key works via `Authorization` header; `api-key` query param failed.
- Finnhub API key validated with AAPL endpoints (quote, profile2, metric, financials-reported, company-news, earnings, recommendation).
