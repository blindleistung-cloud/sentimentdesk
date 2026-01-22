from __future__ import annotations

from app.config.settings import Settings
from app.schemas.report import LayerInput, RuleTraceEntry, ScoreResult


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_layers(layers: LayerInput, settings: Settings) -> ScoreResult:
    trace: list[RuleTraceEntry] = []

    valuation_score = 100.0
    thresholds = settings.valuation_thresholds

    for stock in layers.valuation.overvalued_stocks:
        over_threshold = False
        if stock.pe_ratio and stock.pe_ratio.value is not None:
            if stock.pe_ratio.value >= thresholds.pe_ratio:
                over_threshold = True
        if stock.pb_ratio and stock.pb_ratio.value is not None:
            if stock.pb_ratio.value >= thresholds.pb_ratio:
                over_threshold = True
        if stock.pcf_ratio and stock.pcf_ratio.value is not None:
            if stock.pcf_ratio.value >= thresholds.pcf_ratio:
                over_threshold = True
        if over_threshold:
            valuation_score -= thresholds.per_stock_weight
            trace.append(
                RuleTraceEntry(
                    rule_id="valuation:over_threshold",
                    field="scores.valuation",
                    value=str(stock.name),
                    detail=f"Applied -{thresholds.per_stock_weight} due to ratio thresholds.",
                )
            )

    valuation_score = clamp(valuation_score)

    capex_score = 50.0
    capex_thresholds = settings.capex_thresholds

    if layers.capex.capex_items:
        increment = capex_thresholds.per_item_weight * len(layers.capex.capex_items)
        capex_score += increment
        trace.append(
            RuleTraceEntry(
                rule_id="capex:items",
                field="scores.capex",
                value=str(len(layers.capex.capex_items)),
                detail=f"Applied +{increment} for capex items.",
            )
        )

    if layers.capex.capex_total_usd_billion is not None:
        if layers.capex.capex_total_usd_billion >= capex_thresholds.total_usd_billion:
            capex_score += capex_thresholds.per_item_weight
            trace.append(
                RuleTraceEntry(
                    rule_id="capex:total",
                    field="scores.capex",
                    value=str(layers.capex.capex_total_usd_billion),
                    detail=f"Applied +{capex_thresholds.per_item_weight} for total capex threshold.",
                )
            )

    capex_score = clamp(capex_score)

    risk_score = 100.0
    risk_thresholds = settings.risk_thresholds
    total_risk_hits = sum(cluster.count for cluster in layers.risk.risk_clusters)
    penalty = total_risk_hits * risk_thresholds.per_hit_weight
    risk_score -= penalty
    risk_score = clamp(risk_score, 0.0, risk_thresholds.max_score)
    trace.append(
        RuleTraceEntry(
            rule_id="risk:keyword_hits",
            field="scores.risk",
            value=str(total_risk_hits),
            detail=f"Applied -{penalty} for risk keyword hits.",
        )
    )

    weights = settings.weights
    composite_score = (
        weights.valuation * valuation_score
        + weights.capex * capex_score
        + weights.risk * risk_score
    )
    composite_score = clamp(composite_score)

    return ScoreResult(
        valuation_score=valuation_score,
        capex_score=capex_score,
        risk_score=risk_score,
        composite_score=composite_score,
        rule_trace=trace,
    )
