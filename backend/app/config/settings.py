from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class WeightSettings(BaseModel):
    valuation: float = 0.4
    capex: float = 0.4
    risk: float = 0.2


class ValuationThresholds(BaseModel):
    pe_ratio: float = 50.0
    pb_ratio: float = 10.0
    pcf_ratio: float = 30.0
    per_stock_weight: float = 10.0


class CapexThresholds(BaseModel):
    total_usd_billion: float = 300.0
    per_item_weight: float = 5.0


class RiskThresholds(BaseModel):
    per_hit_weight: float = 2.0
    max_score: float = 100.0


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTIMENTDESK_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    simfin_api_key: str | None = None
    finnhub_api_key: str | None = None


class ParserSettings(BaseModel):
    risk_keywords: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "geopolitics": ["geopolit", "zoll", "trade", "tariff", "krieg"],
            "rates": ["zins", "rate", "fed", "yield"],
            "capex": ["capex", "invest", "infrastruktur", "ai"],
            "valuation": ["bewert", "overvalu", "kgv", "kbv", "kcv", "p/e", "p/b", "p/cf"],
            "concentration": ["konzentr", "megacap", "magnificent", "top 6"],
            "supply_chain": ["lieferkett", "supply", "strom", "gpu", "engpass"],
        }
    )
    index_names: List[str] = Field(
        default_factory=lambda: [
            "DAX",
            "S&P 500",
            "Nasdaq",
            "Russell 2000",
            "S&P Midcap 400",
            "Euro Stoxx 50",
            "Stoxx Europe 600",
        ]
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTIMENTDESK_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost/sentimentdesk",
        validation_alias=AliasChoices("DATABASE_URL", "SENTIMENTDESK_DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "SENTIMENTDESK_REDIS_URL"),
    )
    provider_queue_name: str = Field(
        default="provider",
        validation_alias=AliasChoices("PROVIDER_QUEUE_NAME", "SENTIMENTDESK_PROVIDER_QUEUE_NAME"),
    )

    weights: WeightSettings = Field(default_factory=WeightSettings)
    valuation_thresholds: ValuationThresholds = Field(default_factory=ValuationThresholds)
    capex_thresholds: CapexThresholds = Field(default_factory=CapexThresholds)
    risk_thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    parser: ParserSettings = Field(default_factory=ParserSettings)


settings = Settings()
