from fastapi import APIRouter

from app.config.settings import settings
from app.parsing.markdown import parse_report
from app.scoring.scoring import score_layers
from app.providers.selector import fetch_with_fallback
from app.schemas.report import ParseRequest, ParseResult, OvervaluedStock

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
def parse_report_endpoint(payload: ParseRequest) -> ParseResult:
    parsed = parse_report(payload.raw_text, settings)
    scores = score_layers(parsed.layers, settings)
    provider_snapshots = []
    for symbol in _extract_symbols(parsed.layers.valuation.overvalued_stocks):
        provider_snapshots.append(fetch_with_fallback(symbol))

    return ParseResult(
        raw_text=payload.raw_text,
        cleaned_text=parsed.cleaned_text,
        layers=parsed.layers,
        scores=scores,
        evidence=parsed.evidence,
        provider_snapshots=provider_snapshots,
    )
