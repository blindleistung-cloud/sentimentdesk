from app.config.settings import settings
from app.providers import finnhub, simfin
from app.providers.selector import fetch_with_fallback


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
    snapshot = finnhub.fetch_snapshot("AAPL", week_id)
    assert snapshot.cache_key == f"finnhub:AAPL:{week_id}"


def test_fetch_with_fallback_cache_key_matches_provider() -> None:
    week_id = "2026-W04"
    previous_key = settings.providers.simfin_api_key
    settings.providers.simfin_api_key = None
    try:
        snapshot = fetch_with_fallback("AAPL", week_id)
    finally:
        settings.providers.simfin_api_key = previous_key
    assert snapshot.cache_key == f"{snapshot.provider}:{snapshot.symbol}:{week_id}"
