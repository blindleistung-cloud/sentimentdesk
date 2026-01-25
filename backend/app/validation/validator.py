from __future__ import annotations

from app.schemas.report import LayerInput, ValidationIssue, ValidationResult


def validate_layers(layers: LayerInput, require_tickers: bool) -> ValidationResult:
    issues: list[ValidationIssue] = []

    stocks = layers.valuation.overvalued_stocks
    if len(stocks) != 5:
        issues.append(
            ValidationIssue(
                field="layers.valuation.overvalued_stocks",
                level="fail",
                message="Expected exactly 5 stocks.",
            )
        )

    missing_names = [stock for stock in stocks if not stock.name.strip()]
    if missing_names:
        issues.append(
            ValidationIssue(
                field="layers.valuation.overvalued_stocks.name",
                level="fail",
                message="Stock names are required.",
            )
        )

    missing_tickers = [
        stock.name for stock in stocks if not (stock.ticker or "").strip()
    ]
    if missing_tickers:
        level = "fail" if require_tickers else "warn"
        issues.append(
            ValidationIssue(
                field="layers.valuation.overvalued_stocks.ticker",
                level=level,
                message="Missing ticker for: " + ", ".join(missing_tickers),
            )
        )

    seen_names: set[str] = set()
    duplicate_names: set[str] = set()
    for stock in stocks:
        name = stock.name.strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen_names:
            duplicate_names.add(name)
        else:
            seen_names.add(key)
    if duplicate_names:
        issues.append(
            ValidationIssue(
                field="layers.valuation.overvalued_stocks.name",
                level="warn",
                message="Duplicate stock names: " + ", ".join(sorted(duplicate_names)),
            )
        )

    for stock in stocks:
        for field_name, ratio in (
            ("pe_ratio", stock.pe_ratio),
            ("pb_ratio", stock.pb_ratio),
            ("pcf_ratio", stock.pcf_ratio),
        ):
            if ratio is None or ratio.value is None:
                continue
            if ratio.value < 0:
                issues.append(
                    ValidationIssue(
                        field=f"layers.valuation.overvalued_stocks.{field_name}",
                        level="warn",
                        message=f"{stock.name}: ratio values must be positive.",
                    )
                )

    if layers.capex.capex_total_usd_billion is not None:
        if layers.capex.capex_total_usd_billion < 0:
            issues.append(
                ValidationIssue(
                    field="layers.capex.capex_total_usd_billion",
                    level="fail",
                    message="Capex total must be positive.",
                )
            )

    if layers.capex.ai_share_percent is not None:
        if layers.capex.ai_share_percent < 0 or layers.capex.ai_share_percent > 100:
            issues.append(
                ValidationIssue(
                    field="layers.capex.ai_share_percent",
                    level="warn",
                    message="AI share should be between 0 and 100.",
                )
            )

    for item in layers.capex.capex_items:
        if item.amount_usd_billion is not None and item.amount_usd_billion < 0:
            issues.append(
                ValidationIssue(
                    field="layers.capex.capex_items.amount_usd_billion",
                    level="fail",
                    message=f"{item.company}: capex amount must be positive.",
                )
            )

        if item.ai_share_percent is not None:
            if item.ai_share_percent < 0 or item.ai_share_percent > 100:
                issues.append(
                    ValidationIssue(
                        field="layers.capex.capex_items.ai_share_percent",
                        level="warn",
                        message=f"{item.company}: AI share should be between 0 and 100.",
                    )
                )

    for cluster in layers.risk.risk_clusters:
        if cluster.count < 0:
            issues.append(
                ValidationIssue(
                    field="layers.risk.risk_clusters.count",
                    level="fail",
                    message=f"{cluster.label}: count must be positive.",
                )
            )

    status = "ok"
    if any(issue.level == "fail" for issue in issues):
        status = "fail"
    elif issues:
        status = "warn"

    return ValidationResult(status=status, issues=issues)
