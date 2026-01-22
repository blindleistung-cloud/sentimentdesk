import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.db.models import Report, MarketDataSnapshot
from app.db.session import get_session
from app.parsing.markdown import parse_report
from app.providers.selector import fetch_with_fallback
from app.schemas.report import OvervaluedStock, ParseRequest, ParseResult
from app.scoring.scoring import score_layers

router = APIRouter()


def _extract_symbols(stocks: list[OvervaluedStock]) -> list[str]:
    symbols: list[str] = []
    for stock in stocks:
        symbol = stock.ticker or stock.name
        if not symbol:
            continue
        symbols.append(symbol)
    return symbols


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/parse", response_model=ParseResult)
async def parse_report_endpoint(
    payload: ParseRequest, db: AsyncSession = Depends(get_session)
) -> ParseResult:
    # 1. Parse and score the report
    parsed = parse_report(payload.raw_text, settings)
    scores = score_layers(parsed.layers, settings)

    # 2. Fetch provider data (currently stubs)
    symbols = _extract_symbols(parsed.layers.valuation.overvalued_stocks)
    provider_snapshots_data = [fetch_with_fallback(symbol) for symbol in symbols]

    # 3. Create and save the report to the database
    week_id = f"{datetime.date.today().isocalendar().year}-W{datetime.date.today().isocalendar().week:02d}"

    db_report = Report(
        week_id=week_id,
        status="processed",
        raw_text=payload.raw_text,
        extracted_inputs=parsed.layers.model_dump(),
        valuation_score=scores.valuation_score,
        capex_score=scores.capex_score,
        risk_score=scores.risk_score,
        composite_score=scores.composite_score,
        rule_trace=scores.model_dump()["rule_trace"],
    )

    # 4. Create snapshot models and associate them
    for snapshot_data in provider_snapshots_data:
        db_snapshot = MarketDataSnapshot(
            provider=snapshot_data.provider,
            symbol=snapshot_data.symbol,
            payload=snapshot_data.payload,
            cache_key=snapshot_data.cache_key,
        )
        db_report.snapshots.append(db_snapshot)

    db.add(db_report)
    await db.commit()
    await db.refresh(db_report)

    # 5. Return the full result
    return ParseResult(
        raw_text=payload.raw_text,
        cleaned_text=parsed.cleaned_text,
        layers=parsed.layers,
        scores=scores,
        evidence=parsed.evidence,
        provider_snapshots=provider_snapshots_data,
    )
