from __future__ import annotations

from app.providers import finnhub, simfin
from app.schemas.provider import MarketDataSnapshot


def fetch_with_fallback(symbol: str, week_id: str) -> MarketDataSnapshot:
    snapshot = simfin.fetch_snapshot(symbol, week_id)
    if snapshot.payload:
        return snapshot
    return finnhub.fetch_snapshot(symbol, week_id)
