import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.db.models import Report
from app.db.session import get_session
from app.jobs.queue import enqueue_provider_fetch
from app.parsing.markdown import parse_report
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

    week_id = f"{datetime.date.today().isocalendar().year}-W{datetime.date.today().isocalendar().week:02d}"

    # 2. Extract provider symbols
    symbols = _extract_symbols(parsed.layers.valuation.overvalued_stocks)

    # 3. Create and save the report to the database
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

    db.add(db_report)
    await db.commit()
    await db.refresh(db_report)

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
