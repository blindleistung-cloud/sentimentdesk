from __future__ import annotations

from app.cache import get_snapshot, set_snapshot
from app.config.settings import settings
from app.schemas.provider import MarketDataSnapshot


def fetch_snapshot(symbol: str, week_id: str) -> MarketDataSnapshot:
    cache_key = f"finnhub:{symbol}:{week_id}"
    cached = get_snapshot(cache_key)
    if cached:
        return cached
    snapshot = MarketDataSnapshot(
        provider="finnhub",
        symbol=symbol,
        cache_key=cache_key,
        status="stub",
    )
    set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
    return snapshot
