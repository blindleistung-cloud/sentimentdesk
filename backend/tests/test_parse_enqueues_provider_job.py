import asyncio
import datetime
import uuid
from unittest.mock import Mock, call, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.routes import manual_report_endpoint, parse_report_endpoint
from app.db.models import Report
from app.parsing.markdown import ParsedContent
from app.schemas.report import (
    LayerAValuation,
    LayerInput,
    ManualReportRequest,
    OvervaluedStock,
    ParseRequest,
    ScoreResult,
)


class FakeResult:
    def __init__(self, report: Report) -> None:
        self.report = report

    def scalar_one(self) -> Report:
        return self.report


class FakeSession:
    def __init__(self, report: Report, week_id: str) -> None:
        self.report = report
        self.week_id = week_id
        self.existing_week_ids: set[str] = set()
        self.used_add = False
        self.last_stmt = None
        self.last_insert_stmt = None
        self.used_execute = False

    def add(self, obj) -> None:
        self.used_add = True

    async def execute(self, stmt) -> FakeResult:
        self.used_execute = True
        self.last_stmt = stmt
        if stmt.__class__.__name__.lower().endswith("insert"):
            self.last_insert_stmt = stmt
        return FakeResult(self.report)

    async def commit(self) -> None:
        if self.used_add and self.week_id in self.existing_week_ids:
            raise IntegrityError("duplicate", None, Exception("duplicate"))
        self.existing_week_ids.add(self.week_id)
        self.used_add = False
        self.used_execute = False

    async def refresh(self, obj) -> None:
        obj.id = self.report.id


def build_overvalued_stocks(missing_ticker: bool = False) -> list[OvervaluedStock]:
    names = ["Test Co", "Second Co", "Third Co", "Fourth Co", "Fifth Co"]
    tickers = ["TST", "T02", "T03", "T04", "T05"]
    stocks: list[OvervaluedStock] = []
    for index, name in enumerate(names):
        ticker = None if missing_ticker and index == 0 else tickers[index]
        stocks.append(OvervaluedStock(rank=index + 1, name=name, ticker=ticker))
    return stocks


def test_parse_enqueues_provider_job() -> None:
    report_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    expected_week_id = (
        f"{datetime.date.today().isocalendar().year}-W"
        f"{datetime.date.today().isocalendar().week:02d}"
    )
    report = Report(id=report_id, week_id=expected_week_id)
    session = FakeSession(report, expected_week_id)

    layers = LayerInput(
        valuation=LayerAValuation(
            overvalued_stocks=build_overvalued_stocks()
        )
    )
    parsed = ParsedContent(cleaned_text="cleaned", layers=layers, evidence=[])
    scores = ScoreResult(
        valuation_score=10.0,
        capex_score=20.0,
        risk_score=30.0,
        composite_score=25.0,
        rule_trace=[],
    )
    job = Mock()
    job.id = "job-123"

    with (
        patch("app.api.routes.parse_report", return_value=parsed),
        patch("app.api.routes.score_layers", return_value=scores),
        patch("app.api.routes.enqueue_provider_fetch", return_value=job) as enqueue_mock,
    ):
        payload = ParseRequest(raw_text="raw text")
        result = asyncio.run(parse_report_endpoint(payload, db=session))
        result_repeat = asyncio.run(parse_report_endpoint(payload, db=session))

    expected_call = call(
        report_id=str(report_id),
        week_id=expected_week_id,
        symbols=["TST", "T02", "T03", "T04", "T05"],
    )
    assert enqueue_mock.call_args_list == [expected_call, expected_call]
    assert result.provider_job_id == "job-123"
    assert result.provider_job_status == "queued"
    assert result.provider_snapshots == []
    assert result_repeat.provider_job_id == "job-123"
    assert result_repeat.provider_job_status == "queued"
    assert result.validation.status == "ok"

    assert session.last_insert_stmt is not None
    update_mapping = session.last_insert_stmt._post_values_clause.update_values_to_set  # type: ignore[attr-defined]
    column_names = {column.name for column, _ in update_mapping}
    assert "extracted_inputs_json" in column_names
    assert "rule_trace_json" in column_names
    assert "validation_status" in column_names
    assert "validation_issues_json" in column_names


def test_parse_applies_ticker_overrides() -> None:
    report_id = uuid.UUID("87654321-4321-8765-4321-876543218765")
    expected_week_id = (
        f"{datetime.date.today().isocalendar().year}-W"
        f"{datetime.date.today().isocalendar().week:02d}"
    )
    report = Report(id=report_id, week_id=expected_week_id)
    session = FakeSession(report, expected_week_id)

    layers = LayerInput(
        valuation=LayerAValuation(
            overvalued_stocks=build_overvalued_stocks(missing_ticker=True)
        )
    )
    parsed = ParsedContent(cleaned_text="cleaned", layers=layers, evidence=[])
    scores = ScoreResult(
        valuation_score=10.0,
        capex_score=20.0,
        risk_score=30.0,
        composite_score=25.0,
        rule_trace=[],
    )
    job = Mock()
    job.id = "job-456"

    with (
        patch("app.api.routes.parse_report", return_value=parsed),
        patch("app.api.routes.score_layers", return_value=scores),
        patch("app.api.routes.enqueue_provider_fetch", return_value=job) as enqueue_mock,
    ):
        payload = ParseRequest(
            raw_text="raw text",
            ticker_overrides=[{"name": " test co ", "ticker": "tstx"}],
        )
        result = asyncio.run(parse_report_endpoint(payload, db=session))

    enqueue_mock.assert_called_once_with(
        report_id=str(report_id),
        week_id=expected_week_id,
        symbols=["TSTX", "T02", "T03", "T04", "T05"],
    )
    assert result.layers.valuation.overvalued_stocks[0].ticker == "TSTX"


def test_parse_warns_on_missing_tickers() -> None:
    report_id = uuid.UUID("99999999-1234-5678-1234-567812345678")
    expected_week_id = (
        f"{datetime.date.today().isocalendar().year}-W"
        f"{datetime.date.today().isocalendar().week:02d}"
    )
    report = Report(id=report_id, week_id=expected_week_id)
    session = FakeSession(report, expected_week_id)

    layers = LayerInput(
        valuation=LayerAValuation(
            overvalued_stocks=build_overvalued_stocks(missing_ticker=True)
        )
    )
    parsed = ParsedContent(cleaned_text="cleaned", layers=layers, evidence=[])
    scores = ScoreResult(
        valuation_score=10.0,
        capex_score=20.0,
        risk_score=30.0,
        composite_score=25.0,
        rule_trace=[],
    )
    job = Mock()
    job.id = "job-789"

    with (
        patch("app.api.routes.parse_report", return_value=parsed),
        patch("app.api.routes.score_layers", return_value=scores),
        patch("app.api.routes.enqueue_provider_fetch", return_value=job),
    ):
        payload = ParseRequest(raw_text="raw text")
        result = asyncio.run(parse_report_endpoint(payload, db=session))

    assert result.validation.status == "warn"
    assert any(
        issue.field == "layers.valuation.overvalued_stocks.ticker"
        for issue in result.validation.issues
    )


def test_manual_report_requires_tickers() -> None:
    report_id = uuid.UUID("22222222-1234-5678-1234-567812345678")
    expected_week_id = (
        f"{datetime.date.today().isocalendar().year}-W"
        f"{datetime.date.today().isocalendar().week:02d}"
    )
    report = Report(id=report_id, week_id=expected_week_id)
    session = FakeSession(report, expected_week_id)

    layers = LayerInput(
        valuation=LayerAValuation(
            overvalued_stocks=build_overvalued_stocks(missing_ticker=True)
        )
    )
    payload = ManualReportRequest(raw_text="raw text", layers=layers)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(manual_report_endpoint(payload, db=session))

    assert excinfo.value.status_code == 400


def test_manual_report_enqueues_provider_job() -> None:
    report_id = uuid.UUID("33333333-1234-5678-1234-567812345678")
    expected_week_id = (
        f"{datetime.date.today().isocalendar().year}-W"
        f"{datetime.date.today().isocalendar().week:02d}"
    )
    report = Report(id=report_id, week_id=expected_week_id)
    session = FakeSession(report, expected_week_id)

    layers = LayerInput(
        valuation=LayerAValuation(overvalued_stocks=build_overvalued_stocks())
    )
    scores = ScoreResult(
        valuation_score=10.0,
        capex_score=20.0,
        risk_score=30.0,
        composite_score=25.0,
        rule_trace=[],
    )
    job = Mock()
    job.id = "job-999"

    with (
        patch("app.api.routes.score_layers", return_value=scores),
        patch("app.api.routes.enqueue_provider_fetch", return_value=job) as enqueue_mock,
    ):
        payload = ManualReportRequest(raw_text="raw text", layers=layers)
        result = asyncio.run(manual_report_endpoint(payload, db=session))

    enqueue_mock.assert_called_once_with(
        report_id=str(report_id),
        week_id=expected_week_id,
        symbols=["TST", "T02", "T03", "T04", "T05"],
    )
    assert result.validation.status == "ok"
