import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.db.models import MarketDataSnapshot, Report, ReportStock, WatchlistItem
from app.db.session import get_session
from app.jobs.queue import enqueue_provider_fetch
from app.parsing.markdown import clean_markdown, extract_stock_mentions, parse_report
from app.schemas.report import (
    ManualReportRequest,
    OvervaluedStock,
    ParseRequest,
    ParseResult,
    StockTickerOverride,
    ValidationResult,
)
from app.schemas.stocks import StockHistoryResponse, StockReportEntry, WeeklyClose
from app.schemas.watchlist import WatchlistItemResponse, WatchlistRequest
from app.scoring.scoring import score_layers
from app.validation.validator import validate_layers

router = APIRouter()
_WEEK_ID_RE = re.compile(r"^\d{4}-W\d{2}$")


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


def _raise_on_validation_fail(validation: ValidationResult) -> None:
    if validation.status == "fail":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Validation failed.",
                "validation": validation.model_dump(),
            },
        )


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _normalize_week_id(week_id: str) -> str:
    cleaned = week_id.strip().upper()
    if not _WEEK_ID_RE.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "week_id must be in YYYY-Www format."},
        )
    return cleaned


def _build_report_stock_rows(
    report_id, stocks: list[OvervaluedStock], mentions: dict[str, list[str]], created_at: datetime.datetime
) -> list[dict]:
    rows: list[dict] = []
    for stock in stocks:
        ticker = _normalize_ticker(stock.ticker or "")
        if not ticker:
            continue
        focus_commentary = (stock.commentary or "").strip() or None
        rows.append(
            {
                "report_id": report_id,
                "ticker": ticker,
                "name": stock.name.strip(),
                "rank": stock.rank,
                "focus_commentary": focus_commentary,
                "mention_snippets": mentions.get(ticker, []),
                "pe_ratio": stock.pe_ratio.value if stock.pe_ratio else None,
                "pb_ratio": stock.pb_ratio.value if stock.pb_ratio else None,
                "pcf_ratio": stock.pcf_ratio.value if stock.pcf_ratio else None,
                "created_at": created_at,
            }
        )
    return rows


async def _persist_report_stocks(
    db: AsyncSession,
    report_id,
    stocks: list[OvervaluedStock],
    mentions: dict[str, list[str]],
    created_at: datetime.datetime,
) -> None:
    await db.execute(delete(ReportStock).where(ReportStock.report_id == report_id))
    rows = _build_report_stock_rows(report_id, stocks, mentions, created_at)
    for row in rows:
        await db.execute(insert(ReportStock).values(**row))
    await db.commit()


def _build_weekly_closes(snapshot: MarketDataSnapshot | None) -> list[WeeklyClose]:
    if snapshot is None or not isinstance(snapshot.payload, dict):
        return []
    times = snapshot.payload.get("t") or []
    closes = snapshot.payload.get("c") or []
    if not isinstance(times, list) or not isinstance(closes, list):
        return []

    weekly_closes: list[WeeklyClose] = []
    for ts_value, close_value in zip(times, closes):
        if not isinstance(ts_value, (int, float)):
            continue
        if not isinstance(close_value, (int, float)):
            continue
        week_start = datetime.datetime.fromtimestamp(
            int(ts_value), tz=datetime.UTC
        ).date()
        weekly_closes.append(WeeklyClose(week_start=week_start, close=float(close_value)))

    weekly_closes.sort(key=lambda entry: entry.week_start)
    return weekly_closes


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/parse", response_model=ParseResult)
async def parse_report_endpoint(
    payload: ParseRequest, db: AsyncSession = Depends(get_session)
) -> ParseResult:
    # 1. Parse and score the report
    parsed = parse_report(payload.raw_text, settings)
    _apply_ticker_overrides(parsed.layers.valuation.overvalued_stocks, payload.ticker_overrides)
    validation = validate_layers(parsed.layers, require_tickers=False)
    _raise_on_validation_fail(validation)
    scores = score_layers(parsed.layers, settings)
    mentions = extract_stock_mentions(
        parsed.cleaned_text, parsed.layers.valuation.overvalued_stocks
    )

    week_id = _normalize_week_id(payload.week_id)
    existing = await db.execute(select(Report).where(Report.week_id == week_id))
    if existing.scalar_one_or_none() and not payload.allow_overwrite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Report for {week_id} already exists. Set allow_overwrite to replace it.",
            },
        )

    # 2. Extract provider symbols
    symbols = _extract_symbols(parsed.layers.valuation.overvalued_stocks)

    # 3. Create or update the report for the week
    now = datetime.datetime.utcnow()
    extracted_inputs = parsed.layers.model_dump()
    rule_trace = scores.model_dump()["rule_trace"]
    validation_issues = [issue.model_dump() for issue in validation.issues]
    insert_values = {
        "week_id": week_id,
        "status": "processed",
        "validation_status": validation.status,
        "raw_text": payload.raw_text,
        "extracted_inputs": extracted_inputs,
        "validation_issues": validation_issues,
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
        Report.validation_status: validation.status,
        Report.raw_text: payload.raw_text,
        Report.extracted_inputs: extracted_inputs,
        Report.validation_issues: validation_issues,
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

    await _persist_report_stocks(
        db,
        db_report.id,
        parsed.layers.valuation.overvalued_stocks,
        mentions,
        now,
    )

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
        validation=validation,
        provider_job_id=provider_job_id,
        provider_job_status=provider_job_status,
        evidence=parsed.evidence,
        provider_snapshots=[],
    )


@router.post("/report/manual", response_model=ParseResult)
async def manual_report_endpoint(
    payload: ManualReportRequest, db: AsyncSession = Depends(get_session)
) -> ParseResult:
    layers = payload.layers
    validation = validate_layers(layers, require_tickers=True)
    _raise_on_validation_fail(validation)
    scores = score_layers(layers, settings)

    week_id = _normalize_week_id(payload.week_id)
    existing = await db.execute(select(Report).where(Report.week_id == week_id))
    if existing.scalar_one_or_none() and not payload.allow_overwrite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Report for {week_id} already exists. Set allow_overwrite to replace it.",
            },
        )
    symbols = _extract_symbols(layers.valuation.overvalued_stocks)
    cleaned_text = clean_markdown(payload.raw_text)
    mentions = extract_stock_mentions(cleaned_text, layers.valuation.overvalued_stocks)

    now = datetime.datetime.utcnow()
    extracted_inputs = layers.model_dump()
    rule_trace = scores.model_dump()["rule_trace"]
    validation_issues = [issue.model_dump() for issue in validation.issues]
    insert_values = {
        "week_id": week_id,
        "status": "processed",
        "validation_status": validation.status,
        "raw_text": payload.raw_text,
        "extracted_inputs": extracted_inputs,
        "validation_issues": validation_issues,
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
        Report.validation_status: validation.status,
        Report.raw_text: payload.raw_text,
        Report.extracted_inputs: extracted_inputs,
        Report.validation_issues: validation_issues,
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

    await _persist_report_stocks(
        db,
        db_report.id,
        layers.valuation.overvalued_stocks,
        mentions,
        now,
    )

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

    return ParseResult(
        raw_text=payload.raw_text,
        cleaned_text=cleaned_text,
        layers=layers,
        scores=scores,
        validation=validation,
        provider_job_id=provider_job_id,
        provider_job_status=provider_job_status,
        evidence=[],
        provider_snapshots=[],
    )


@router.get("/watchlist", response_model=list[WatchlistItemResponse])
async def list_watchlist(db: AsyncSession = Depends(get_session)) -> list[WatchlistItemResponse]:
    result = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.active.is_(True))
        .order_by(WatchlistItem.added_at.desc())
    )
    items = result.scalars().all()
    return [
        WatchlistItemResponse(
            ticker=item.ticker,
            name=item.name,
            active=item.active,
            added_at=item.added_at,
            removed_at=item.removed_at,
        )
        for item in items
    ]


@router.post("/watchlist", response_model=WatchlistItemResponse)
async def add_watchlist_item(
    payload: WatchlistRequest, db: AsyncSession = Depends(get_session)
) -> WatchlistItemResponse:
    ticker = _normalize_ticker(payload.ticker)
    if not ticker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker is required.",
        )
    name = payload.name.strip() or ticker
    now = datetime.datetime.utcnow()
    insert_values = {
        "ticker": ticker,
        "name": name,
        "active": True,
        "added_at": now,
        "removed_at": None,
    }
    update_values = {
        WatchlistItem.name: name,
        WatchlistItem.active: True,
        WatchlistItem.removed_at: None,
    }
    stmt = insert(WatchlistItem).values(**insert_values)
    stmt = stmt.on_conflict_do_update(index_elements=[WatchlistItem.ticker], set_=update_values)
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker))
    item = result.scalar_one()
    return WatchlistItemResponse(
        ticker=item.ticker,
        name=item.name,
        active=item.active,
        added_at=item.added_at,
        removed_at=item.removed_at,
    )


@router.delete("/watchlist/{ticker}", response_model=WatchlistItemResponse)
async def remove_watchlist_item(
    ticker: str, db: AsyncSession = Depends(get_session)
) -> WatchlistItemResponse:
    normalized = _normalize_ticker(ticker)
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == normalized))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    item.active = False
    item.removed_at = datetime.datetime.utcnow()
    await db.commit()

    return WatchlistItemResponse(
        ticker=item.ticker,
        name=item.name,
        active=item.active,
        added_at=item.added_at,
        removed_at=item.removed_at,
    )


@router.get("/stocks/{ticker}", response_model=StockHistoryResponse)
async def get_stock_history(
    ticker: str, db: AsyncSession = Depends(get_session)
) -> StockHistoryResponse:
    normalized = _normalize_ticker(ticker)

    watchlist_result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.ticker == normalized)
    )
    watchlist_item = watchlist_result.scalar_one_or_none()
    watchlist_active = bool(watchlist_item and watchlist_item.active)
    watchlist_added_at = watchlist_item.added_at if watchlist_item else None

    report_stmt = (
        select(ReportStock, Report)
        .join(Report, ReportStock.report_id == Report.id)
        .where(ReportStock.ticker == normalized)
        .order_by(Report.created_at.desc())
    )
    report_rows = await db.execute(report_stmt)
    entries: list[StockReportEntry] = []
    name = watchlist_item.name if watchlist_item else None
    for report_stock, report in report_rows.all():
        if name is None:
            name = report_stock.name
        mention_snippets = report_stock.mention_snippets or []
        entries.append(
            StockReportEntry(
                week_id=report.week_id,
                report_id=str(report.id),
                rank=report_stock.rank,
                focus_commentary=report_stock.focus_commentary,
                mention_snippets=mention_snippets,
                pe_ratio=report_stock.pe_ratio,
                pb_ratio=report_stock.pb_ratio,
                pcf_ratio=report_stock.pcf_ratio,
                created_at=report.created_at,
            )
        )

    snapshot_stmt = (
        select(MarketDataSnapshot)
        .where(
            MarketDataSnapshot.provider == "finnhub",
            MarketDataSnapshot.symbol == normalized,
            MarketDataSnapshot.cache_key.like(f"finnhub:candles:{normalized}:%"),
        )
        .order_by(MarketDataSnapshot.created_at.desc())
        .limit(1)
    )
    snapshot_result = await db.execute(snapshot_stmt)
    snapshot = snapshot_result.scalar_one_or_none()
    weekly_closes = _build_weekly_closes(snapshot)

    return StockHistoryResponse(
        ticker=normalized,
        name=name,
        watchlist_active=watchlist_active,
        watchlist_added_at=watchlist_added_at,
        report_entries=entries,
        weekly_closes=weekly_closes,
    )
