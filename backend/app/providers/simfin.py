from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config.settings import settings
from app.cache import get_snapshot, set_snapshot
from app.schemas.provider import MarketDataSnapshot


_GENERAL_PATH = "/api/v3/companies/general/compact"


def _build_url(params: dict[str, str]) -> str:
    base_url = settings.providers.simfin_base_url.rstrip("/")
    return f"{base_url}{_GENERAL_PATH}?{urlencode(params)}"


def fetch_snapshot(symbol: str, week_id: str) -> MarketDataSnapshot:
    cache_key = f"simfin:{symbol}:{week_id}"
    cached = get_snapshot(cache_key)
    if cached:
        return cached
    api_key = settings.providers.simfin_api_key
    if not api_key:
        snapshot = MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="missing_key",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    url = _build_url({"ticker": symbol})
    request = Request(url, headers={"Authorization": api_key})
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
    except HTTPError as exc:
        status = "rate_limited" if exc.code == 429 else "error"
        snapshot = MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status=status,
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot
    except (URLError, json.JSONDecodeError, TimeoutError, socket.timeout):
        snapshot = MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    if not isinstance(payload, dict):
        payload = {"data": payload}
    if "data" not in payload:
        snapshot = MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot
    if not payload.get("data"):
        snapshot = MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="empty",
        )
        set_snapshot(snapshot, settings.provider_cache_error_ttl_seconds)
        return snapshot

    snapshot = MarketDataSnapshot(
        provider="simfin",
        symbol=symbol,
        cache_key=cache_key,
        payload=payload,
        status="ok",
    )
    set_snapshot(snapshot, settings.provider_cache_ttl_seconds)
    return snapshot


def check_api_key(probe_id: str | None = None) -> tuple[bool, int | None]:
    api_key = settings.providers.simfin_api_key
    if not api_key:
        return False, None

    probe = probe_id or settings.providers.simfin_probe_id
    url = _build_url({"id": probe})
    request = Request(url, headers={"Authorization": api_key})
    try:
        with urlopen(request, timeout=10) as response:
            return response.status == 200, response.status
    except HTTPError as exc:
        return False, exc.code
    except (URLError, TimeoutError, socket.timeout):
        return False, None
