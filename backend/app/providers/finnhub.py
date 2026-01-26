from __future__ import annotations

import datetime
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.cache import get_snapshot, set_snapshot
from app.config.settings import settings
from app.schemas.provider import MarketDataSnapshot


_QUOTE_PATH = "/api/v1/quote"
_CANDLE_PATH = "/api/v1/stock/candle"


def _build_url(path: str, params: dict[str, str]) -> str:
    return f"https://finnhub.io{path}?{urlencode(params)}"


def fetch_snapshot(symbol: str, week_id: str) -> MarketDataSnapshot:
    cache_key = f"finnhub:quote:{symbol}:{week_id}"
    cached = get_snapshot(cache_key)
    if cached:
        return cached
    api_key = settings.providers.finnhub_api_key
    if not api_key:
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="missing_key",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    url = _build_url(_QUOTE_PATH, {"symbol": symbol, "token": api_key})
    request = Request(url)
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
    except HTTPError as exc:
        status = "rate_limited" if exc.code == 429 else "error"
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status=status,
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot
    except (URLError, json.JSONDecodeError, TimeoutError, socket.timeout):
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    if not isinstance(payload, dict):
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    has_values = payload.get("c") is not None or payload.get("pc") is not None
    if not has_values:
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="empty",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    payload["type"] = "quote"
    snapshot = MarketDataSnapshot(
        provider="finnhub",
        symbol=symbol,
        cache_key=cache_key,
        payload=payload,
        status="ok",
    )
    set_snapshot(snapshot, settings.provider_cache_ttl_seconds)
    return snapshot


def fetch_weekly_candles(
    symbol: str, start_date: datetime.date, end_date: datetime.date
) -> MarketDataSnapshot:
    start_ts = int(
        datetime.datetime.combine(
            start_date, datetime.time.min, tzinfo=datetime.UTC
        ).timestamp()
    )
    end_ts = int(
        datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.UTC).timestamp()
    )
    cache_key = f"finnhub:candles:{symbol}:{start_ts}:{end_ts}"
    cached = get_snapshot(cache_key)
    if cached:
        return cached

    api_key = settings.providers.finnhub_api_key
    if not api_key:
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="missing_key",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    url = _build_url(
        _CANDLE_PATH,
        {
            "symbol": symbol,
            "resolution": "W",
            "from": str(start_ts),
            "to": str(end_ts),
            "token": api_key,
        },
    )
    request = Request(url)
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
    except HTTPError as exc:
        status = "rate_limited" if exc.code == 429 else "error"
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status=status,
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot
    except (URLError, json.JSONDecodeError, TimeoutError, socket.timeout):
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    if not isinstance(payload, dict):
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    if payload.get("s") != "ok":
        snapshot = MarketDataSnapshot(
            provider="finnhub",
            symbol=symbol,
            cache_key=cache_key,
            status="empty",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    payload["type"] = "candles"
    snapshot = MarketDataSnapshot(
        provider="finnhub",
        symbol=symbol,
        cache_key=cache_key,
        payload=payload,
        status="ok",
    )
    set_snapshot(snapshot, settings.provider_cache_ttl_seconds)
    return snapshot
