from __future__ import annotations

from app.schemas.provider import MarketDataSnapshot


def fetch_snapshot(symbol: str) -> MarketDataSnapshot:
    return MarketDataSnapshot(provider="simfin", symbol=symbol)
