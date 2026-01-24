from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config.settings import settings
from app.schemas.provider import MarketDataSnapshot


_GENERAL_PATH = "/api/v3/companies/general/compact"


def _build_url(params: dict[str, str]) -> str:
    base_url = settings.providers.simfin_base_url.rstrip("/")
    return f"{base_url}{_GENERAL_PATH}?{urlencode(params)}"


def fetch_snapshot(symbol: str, week_id: str) -> MarketDataSnapshot:
    cache_key = f"simfin:{symbol}:{week_id}"
    api_key = settings.providers.simfin_api_key
    if not api_key:
        return MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="missing_key",
        )

    url = _build_url({"ticker": symbol})
    request = Request(url, headers={"Authorization": api_key})
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
    except HTTPError as exc:
        status = "rate_limited" if exc.code == 429 else "error"
        return MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status=status,
        )
    except (URLError, json.JSONDecodeError, TimeoutError, socket.timeout):
        return MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )

    if not isinstance(payload, dict):
        payload = {"data": payload}
    if "data" not in payload:
        return MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="error",
        )
    if not payload.get("data"):
        return MarketDataSnapshot(
            provider="simfin",
            symbol=symbol,
            cache_key=cache_key,
            status="empty",
        )

    return MarketDataSnapshot(
        provider="simfin",
        symbol=symbol,
        cache_key=cache_key,
        payload=payload,
        status="ok",
    )


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
