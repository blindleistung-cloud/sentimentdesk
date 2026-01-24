import asyncio
import datetime
import uuid
from unittest.mock import Mock, patch

from app.api.routes import parse_report_endpoint
from app.parsing.markdown import ParsedContent
from app.schemas.report import LayerAValuation, LayerInput, OvervaluedStock, ParseRequest, ScoreResult


class FakeSession:
    def __init__(self, report_id: uuid.UUID) -> None:
        self.report_id = report_id
        self.added = None

    def add(self, obj) -> None:
        self.added = obj

    async def commit(self) -> None:
        return None

    async def refresh(self, obj) -> None:
        obj.id = self.report_id


def test_parse_enqueues_provider_job() -> None:
    report_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    session = FakeSession(report_id)

    layers = LayerInput(
        valuation=LayerAValuation(
            overvalued_stocks=[OvervaluedStock(rank=1, name="Test Co", ticker="TST")]
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

    expected_week_id = (
        f"{datetime.date.today().isocalendar().year}-W"
        f"{datetime.date.today().isocalendar().week:02d}"
    )
    enqueue_mock.assert_called_once_with(
        report_id=str(report_id),
        week_id=expected_week_id,
        symbols=["TST"],
    )
    assert result.provider_job_id == "job-123"
    assert result.provider_job_status == "queued"
    assert result.provider_snapshots == []
