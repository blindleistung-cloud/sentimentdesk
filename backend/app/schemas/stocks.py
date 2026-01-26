from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class WeeklyClose(BaseModel):
    week_start: datetime.date
    close: float


class StockReportEntry(BaseModel):
    week_id: str
    report_id: str
    rank: int | None = None
    focus_commentary: str | None = None
    mention_snippets: list[str] = Field(default_factory=list)
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    pcf_ratio: float | None = None
    created_at: datetime.datetime | None = None


class StockHistoryResponse(BaseModel):
    ticker: str
    name: str | None = None
    watchlist_active: bool
    watchlist_added_at: datetime.datetime | None = None
    report_entries: list[StockReportEntry] = Field(default_factory=list)
    weekly_closes: list[WeeklyClose] = Field(default_factory=list)
