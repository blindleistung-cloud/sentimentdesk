from __future__ import annotations

import json

from redis import Redis

from app.config.settings import settings
from app.schemas.provider import MarketDataSnapshot


def _get_client() -> Redis:
    return Redis.from_url(settings.redis_url)


def get_snapshot(cache_key: str) -> MarketDataSnapshot | None:
    try:
        client = _get_client()
        raw = client.get(cache_key)
    except Exception:
        return None

    if not raw:
        return None

    try:
        payload = json.loads(raw)
        return MarketDataSnapshot(**payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def set_snapshot(snapshot: MarketDataSnapshot, ttl_seconds: int) -> None:
    try:
        client = _get_client()
        client.setex(snapshot.cache_key, ttl_seconds, snapshot.model_dump_json())
    except Exception:
        return None
