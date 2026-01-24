from app.cache import get_snapshot, set_snapshot
from app.schemas.provider import MarketDataSnapshot


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.expirations[key] = ttl


def test_cache_roundtrip(monkeypatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr("app.cache._get_client", lambda: fake)

    snapshot = MarketDataSnapshot(
        provider="simfin",
        symbol="AAPL",
        cache_key="simfin:AAPL:2026-W04",
        payload={"data": [{"foo": "bar"}]},
        status="ok",
    )

    set_snapshot(snapshot, ttl_seconds=123)
    cached = get_snapshot(snapshot.cache_key)

    assert cached is not None
    assert cached.cache_key == snapshot.cache_key
    assert cached.payload == snapshot.payload
    assert fake.expirations[snapshot.cache_key] == 123
