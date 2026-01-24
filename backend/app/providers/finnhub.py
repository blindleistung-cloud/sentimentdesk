from __future__ import annotations

from app.schemas.provider import MarketDataSnapshot


def fetch_snapshot(symbol: str, week_id: str) -> MarketDataSnapshot:
    cache_key = f"finnhub:{symbol}:{week_id}"
    return MarketDataSnapshot(provider="finnhub", symbol=symbol, cache_key=cache_key)
