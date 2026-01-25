import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.db.models import Report
from app.db.session import get_session
from app.jobs.queue import enqueue_provider_fetch
from app.parsing.markdown import parse_report
from app.schemas.report import OvervaluedStock, ParseRequest, ParseResult, StockTickerOverride
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


def _normalize_name(name: str) -> str:
    return name.strip().casefold()


def _apply_ticker_overrides(
    stocks: list[OvervaluedStock], overrides: list[StockTickerOverride]
) -> None:
    if not overrides:
        return
    override_map: dict[str, str] = {}
    for override in overrides:
        name = override.name.strip()
        if not name:
            continue
        ticker = (override.ticker or "").strip()
        if not ticker:
            continue
        override_map[_normalize_name(name)] = ticker.upper()
    if not override_map:
        return
    for stock in stocks:
        key = _normalize_name(stock.name)
        if key in override_map:
            stock.ticker = override_map[key]


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

    week_id = f"{datetime.date.today().isocalendar().year}-W{datetime.date.today().isocalendar().week:02d}"

    # 2. Extract provider symbols
    _apply_ticker_overrides(parsed.layers.valuation.overvalued_stocks, payload.ticker_overrides)
    symbols = _extract_symbols(parsed.layers.valuation.overvalued_stocks)

    # 3. Create or update the report for the week
    now = datetime.datetime.now(datetime.UTC)
    extracted_inputs = parsed.layers.model_dump()
    rule_trace = scores.model_dump()["rule_trace"]
    insert_values = {
        "week_id": week_id,
        "status": "processed",
        "raw_text": payload.raw_text,
        "extracted_inputs": extracted_inputs,
        "valuation_score": scores.valuation_score,
        "capex_score": scores.capex_score,
        "risk_score": scores.risk_score,
        "composite_score": scores.composite_score,
        "rule_trace": rule_trace,
        "created_at": now,
        "updated_at": now,
    }
    update_values = {
        Report.status: "processed",
        Report.raw_text: payload.raw_text,
        Report.extracted_inputs: extracted_inputs,
        Report.valuation_score: scores.valuation_score,
        Report.capex_score: scores.capex_score,
        Report.risk_score: scores.risk_score,
        Report.composite_score: scores.composite_score,
        Report.rule_trace: rule_trace,
        Report.updated_at: now,
    }
    stmt = insert(Report).values(**insert_values)
    stmt = stmt.on_conflict_do_update(index_elements=[Report.week_id], set_=update_values)
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(select(Report).where(Report.week_id == week_id))
    db_report = result.scalar_one()

    provider_job_id = None
    provider_job_status = None
    if symbols:
        job = enqueue_provider_fetch(
            report_id=str(db_report.id),
            week_id=week_id,
            symbols=symbols,
        )
        provider_job_id = job.id
        provider_job_status = "queued"

    # 5. Return the full result
    return ParseResult(
        raw_text=payload.raw_text,
        cleaned_text=parsed.cleaned_text,
        layers=parsed.layers,
        scores=scores,
        provider_job_id=provider_job_id,
        provider_job_status=provider_job_status,
        evidence=parsed.evidence,
        provider_snapshots=[],
    )
