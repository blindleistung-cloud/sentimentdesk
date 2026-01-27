from unittest.mock import patch

from app.config.settings import settings
from app.providers import finnhub, simfin
from app.providers.selector import fetch_with_fallback
from app.schemas.provider import MarketDataSnapshot


def test_simfin_snapshot_cache_key() -> None:
    week_id = "2026-W04"
    previous_key = settings.providers.simfin_api_key
    settings.providers.simfin_api_key = None
    try:
        snapshot = simfin.fetch_snapshot("AAPL", week_id)
    finally:
        settings.providers.simfin_api_key = previous_key
    assert snapshot.cache_key == f"simfin:AAPL:{week_id}"


def test_finnhub_snapshot_cache_key() -> None:
    week_id = "2026-W04"
    previous_key = settings.providers.finnhub_api_key
    settings.providers.finnhub_api_key = None
    try:
        snapshot = finnhub.fetch_snapshot("AAPL", week_id)
    finally:
        settings.providers.finnhub_api_key = previous_key
    assert snapshot.cache_key == f"finnhub:quote:AAPL:{week_id}"


def test_fetch_with_fallback_cache_key_matches_provider() -> None:
    week_id = "2026-W04"
    previous_simfin_key = settings.providers.simfin_api_key
    previous_finnhub_key = settings.providers.finnhub_api_key
    settings.providers.simfin_api_key = None
    settings.providers.finnhub_api_key = None
    try:
        snapshot = fetch_with_fallback("AAPL", week_id)
    finally:
        settings.providers.simfin_api_key = previous_simfin_key
        settings.providers.finnhub_api_key = previous_finnhub_key
    assert snapshot.cache_key == f"finnhub:quote:AAPL:{week_id}"


def test_fetch_with_fallback_uses_finnhub_for_index_symbols() -> None:
    week_id = "2026-W04"
    index_symbol = next(iter(settings.market_index_symbols.values()))
    simfin_snapshot = MarketDataSnapshot(
        provider="simfin",
        symbol=index_symbol,
        cache_key=f"simfin:{index_symbol}:{week_id}",
        payload={"data": {"stub": True}},
        status="ok",
    )
    finnhub_snapshot = MarketDataSnapshot(
        provider="finnhub",
        symbol=index_symbol,
        cache_key=f"finnhub:{index_symbol}:{week_id}",
        payload={"c": 1.0},
        status="ok",
    )
    with patch(
        "app.providers.selector.simfin.fetch_snapshot", return_value=simfin_snapshot
    ) as simfin_mock, patch(
        "app.providers.selector.finnhub.fetch_snapshot", return_value=finnhub_snapshot
    ) as finnhub_mock:
        snapshot = fetch_with_fallback(index_symbol, week_id)

    assert snapshot.provider == "finnhub"
    assert snapshot.cache_key == f"finnhub:{index_symbol}:{week_id}"
    assert finnhub_mock.called is True
    assert simfin_mock.called is False
