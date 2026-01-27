from __future__ import annotations

from app.config.settings import settings
from app.providers import finnhub, simfin
from app.schemas.provider import MarketDataSnapshot


def _is_index_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    index_symbols = {
        value.strip().upper() for value in settings.market_index_symbols.values()
    }
    return normalized in index_symbols


def fetch_with_fallback(symbol: str, week_id: str) -> MarketDataSnapshot:
    if _is_index_symbol(symbol):
        return finnhub.fetch_snapshot(symbol, week_id)
    snapshot = simfin.fetch_snapshot(symbol, week_id)
    if snapshot.payload:
        return snapshot
    return finnhub.fetch_snapshot(symbol, week_id)
