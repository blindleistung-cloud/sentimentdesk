from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.provider import MarketDataSnapshot


class EvidenceMatch(BaseModel):
    field: str
    rule_id: str
    pattern: str
    snippet: str


class RatioValue(BaseModel):
    value: Optional[float] = None
    raw: Optional[str] = None


class OvervaluedStock(BaseModel):
    rank: int
    name: str
    ticker: Optional[str] = None
    pe_ratio: Optional[RatioValue] = None
    pb_ratio: Optional[RatioValue] = None
    pcf_ratio: Optional[RatioValue] = None
    evidence: list[EvidenceMatch] = Field(default_factory=list)


class LayerAValuation(BaseModel):
    overvalued_stocks: list[OvervaluedStock] = Field(default_factory=list)


class CapexItem(BaseModel):
    company: str
    year: Optional[int] = None
    amount_usd_billion: Optional[float] = None
    ai_share_percent: Optional[float] = None
    evidence: list[EvidenceMatch] = Field(default_factory=list)


class LayerBCapex(BaseModel):
    capex_items: list[CapexItem] = Field(default_factory=list)
    capex_total_usd_billion: Optional[float] = None
    ai_share_percent: Optional[float] = None


class RiskCluster(BaseModel):
    label: str
    count: int
    evidence: list[EvidenceMatch] = Field(default_factory=list)


class LayerCRisk(BaseModel):
    risk_clusters: list[RiskCluster] = Field(default_factory=list)


class IndexMove(BaseModel):
    index: str
    percent_change: Optional[float] = None
    points_change: Optional[float] = None
    direction: Optional[Literal["up", "down", "flat"]] = None
    evidence: list[EvidenceMatch] = Field(default_factory=list)


class LayerDMarketContext(BaseModel):
    week_label: Optional[str] = None
    index_moves: list[IndexMove] = Field(default_factory=list)


class LayerInput(BaseModel):
    valuation: LayerAValuation = Field(default_factory=LayerAValuation)
    capex: LayerBCapex = Field(default_factory=LayerBCapex)
    risk: LayerCRisk = Field(default_factory=LayerCRisk)
    market_context: LayerDMarketContext = Field(default_factory=LayerDMarketContext)


class RuleTraceEntry(BaseModel):
    rule_id: str
    field: str
    value: str
    detail: str


class ScoreResult(BaseModel):
    valuation_score: float
    capex_score: float
    risk_score: float
    composite_score: float
    rule_trace: list[RuleTraceEntry] = Field(default_factory=list)


class ParseRequest(BaseModel):
    raw_text: str


ProviderJobStatus = Literal["queued", "running", "finished", "failed"]


class ParseResult(BaseModel):
    raw_text: str
    cleaned_text: str
    layers: LayerInput
    scores: ScoreResult
    provider_job_id: Optional[str] = None
    provider_job_status: Optional[ProviderJobStatus] = None
    provider_snapshots: list[MarketDataSnapshot] = Field(default_factory=list)
    evidence: list[EvidenceMatch] = Field(default_factory=list)
