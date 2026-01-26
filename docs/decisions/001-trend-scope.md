# Decision 001: Trend Scope and Metrics

## Status
Accepted (v1)

## Context
Weekly reports are the manual, deterministic input. The real value of SentimentDesk is to
track per-stock trend shifts over time, not just store weekly snapshots.

## Decision
- Scope: per-stock trends only (no sector/theme trends in v1).
- Window: rolling 4+ week trend horizon.
- Input governance: one report per calendar week (explicit week_id); overwrite requires explicit confirmation.
- Provider metrics: use provider-computed valuation ratios (PE/PB/PCF).
- Capex trend: trailing-12-month capex trend per stock.
- Output: dashboard-only (no exports or alerts beyond UI).

## Consequences
- Provider normalization must expose PE/PB/PCF and TTM capex per stock.
- Trend scoring rules must be deterministic and configurable in Settings.
