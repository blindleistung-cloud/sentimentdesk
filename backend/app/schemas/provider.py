from pydantic import BaseModel, Field


class MarketDataSnapshot(BaseModel):
    provider: str
    symbol: str
    cache_key: str
    payload: dict = Field(default_factory=dict)
    status: str = "stub"
