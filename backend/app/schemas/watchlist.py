from __future__ import annotations

import datetime

from pydantic import BaseModel


class WatchlistRequest(BaseModel):
    ticker: str
    name: str


class WatchlistItemResponse(BaseModel):
    ticker: str
    name: str
    active: bool
    added_at: datetime.datetime
    removed_at: datetime.datetime | None = None
