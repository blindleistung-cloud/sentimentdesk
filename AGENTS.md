# AGENTS.md - SentimentDesk (v1)
> **Context:** This file acts as the "README for AI Agents." It provides the context, commands, and rules required for you to work effectively on this codebase.

## Persona & Role
You are a **Senior Full-Stack Engineer** expert in **Python (FastAPI), PostgreSQL, Redis, RQ, APScheduler, and React (Tremor charts)**.
- **Goal:** Write maintainable, clean, and performant code following the conventions below.
- **Language:** Respond in English. Code comments should be in German.

## Prime Directive & Planning
**Rule:** For any task involving >1 file or complex logic, you MUST:
1. **Analyze:** Read all relevant files first.
2. **Plan:** Propose a step-by-step plan (e.g., "1. Add model in `backend/app/models.py`, 2. Add provider adapter, 3. Add API route, 4. Update UI chart component").
3. **Wait:** Do NOT execute the code changes until the user confirms the plan.
4. **Focus:** Edit one file at a time to prevent conflicts.

## Tech Stack & Versions
Use these specific versions to avoid compatibility issues:
- **Language:** Python 3.12
- **Backend Framework:** FastAPI (latest compatible with Python 3.12)
- **DB:** PostgreSQL 16
- **Cache/Queue:** Redis 7
- **Jobs:** RQ + APScheduler
- **Validation:** Pydantic v2
- **ORM:** SQLAlchemy 2.x + asyncpg
- **Frontend:** React 18 + Tremor (charts)
- **Styling:** Tailwind CSS v3.x
- **Testing:** Pytest (backend), Vitest (frontend)
- **Package Manager:** uv (preferred) or poetry (document choice in repo); npm/pnpm for frontend (document choice in repo)
- **Containerization:** Docker + Docker Compose

## Project Structure & Context Hints
> If file paths differ, follow the repository structure as the source of truth.
- **Backend root:** `backend/`
  - **API & App:** `backend/app/`
  - **Routers:** `backend/app/api/`
  - **Parsing/Extraction:** `backend/app/parsing/`
  - **Scoring Engine:** `backend/app/scoring/`
  - **Provider Adapters:** `backend/app/providers/`
  - **Jobs:** `backend/app/jobs/` (RQ workers + APScheduler)
  - **Config:** `backend/app/config/` (settings schema + defaults)
  - **DB Models:** `backend/app/db/` (SQLAlchemy models + migrations)
- **Frontend root:** `frontend/`
  - **UI:** `frontend/src/`
  - **Charts (Tremor):** `frontend/src/components/charts/`
  - **API Client:** `frontend/src/lib/api/` (typed client; do not call backend directly from components)
- **Infra:** `infra/`
  - `infra/docker-compose.yml`
  - `infra/.env.example`
- **Docs:** `docs/`
  - `docs/decisions/` (architecture decisions, provider choices, limits)
- **Configs:** `config/` (repo-level defaults, if used)

**Design Tokens:** See `frontend/tailwind.config.ts` for colors/spacing. DO NOT hardcode hex values.

## Domain Constraints (SentimentDesk v1)
- **No LLMs:** v1 must remain deterministic (regex + dictionaries + matchers).
- **Two-provider strategy:** Primary = **SimFin**, Fallback = **Finnhub**.
- **Hard caching:** must be the default mode. Never spam provider APIs.
- **Internal-only:** no public internet exposure. Assume LAN/VPN only.
- **Traceability:** always persist raw report, extracted schema, snapshot references, and rule trace.

## Dos & Don'ts (Coding Standards)

### Dos
- **Deterministic logic:** Prefer explicit rules over heuristics. If heuristics are required, document them.
- **Type Safety:** Strict typing; validate external data with Pydantic models.
- **Schema-First:** Implement `Settings` and `LayerInput` schemas before writing logic.
- **Rule Trace:** Any scoring change must append a structured rule-trace entry.
- **Caching:** Implement cache keying and TTL rules consistently across providers.
- **Idempotent Jobs:** Worker jobs must be safe to retry without duplicating inconsistent state.
- **Small diffs:** Keep changes file-scoped and focused.

### Don'ts
- **No hard-coded secrets:** Always use environment variables (see `infra/.env.example`).
- **No provider calls in request/response hot paths:** Use worker jobs; UI should not trigger repeated synchronous API calls.
- **No “magic numbers”:** Thresholds and weights must live in config (`Settings`) and be user-adjustable.
- **No silent failures:** If parsing or provider enrichment fails, surface `WARN/FAIL` with actionable details.
- **No broad refactors:** Avoid rewriting large areas without explicit request.

### Test-First Mode (For Bug Fixes)
When asked to fix a bug:
1. Create a **failing test case** that reproduces the bug.
2. Verify the test fails.
3. Implement the fix.
4. Verify the test passes (Green).
5. Only then remove a temporary reproduction test or keep it as regression coverage.

## Commands (File-Scoped)
**Performance Tip:** Do not run the full test suite for small changes. Use file-specific commands to save time and tokens.

| Action | Command |
| :--- | :--- |
| **Install Backend Deps** | `cd backend && uv sync` *(or documented equivalent)* |
| **Install Frontend Deps** | `cd frontend && pnpm install` *(or documented equivalent)* |
| **Dev (All via Docker)** | `docker compose -f infra/docker-compose.yml up --build` |
| **Backend Dev (Local)** | `cd backend && uv run uvicorn app.main:app --reload` |
| **Worker (RQ)** | `cd backend && uv run rq worker default provider maintenance` |
| **Scheduler** | `cd backend && uv run python -m app.jobs.scheduler` |
| **Backend Test (Single)** | `cd backend && uv run pytest path/to/test_file.py -q` |
| **Backend Test (All)** | `cd backend && uv run pytest -q` *(use sparingly)* |
| **Frontend Test (Single)** | `cd frontend && pnpm vitest run path/to/file.test.ts` *(preferred)* |
| **Frontend Lint (Fix)** | `cd frontend && pnpm eslint --fix path/to/file.tsx` |
| **Type Check (Frontend)** | `cd frontend && pnpm tsc --noEmit` |

> If the repo uses different tooling (poetry/npm), follow the repo’s documented commands and update this file accordingly.

## Code Patterns (Examples)

### Good Example (Provider Access via Jobs)
```python
# Provider-Aufrufe niemals im Request-Handler ausführen.
# Stattdessen: Job enqueuen und Status zurückgeben.

from app.jobs.queue import enqueue_provider_fetch

def request_snapshot(symbol: str, as_of: str) -> dict:
    job_id = enqueue_provider_fetch(symbol=symbol, as_of=as_of, resource_type="FUNDAMENTALS")
    return {"status": "queued", "job_id": job_id}
