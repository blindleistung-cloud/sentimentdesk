from __future__ import annotations

import asyncio
import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config.settings import settings
from app.db.models import MarketDataSnapshot, Report, WatchlistItem
from app.db.session import AsyncSessionLocal
from app.providers import finnhub
from app.providers.selector import fetch_with_fallback
from app.schemas.report import IndexMove


async def _fetch_and_store(report_id: str, week_id: str, symbols: list[str]) -> int:
    report_uuid = uuid.UUID(report_id)
    async with AsyncSessionLocal() as session:
        report = await session.get(Report, report_uuid)
        if report is None:
            return 0

        watchlist_result = await session.execute(
            select(WatchlistItem).where(WatchlistItem.active.is_(True))
        )
        watchlist_items = watchlist_result.scalars().all()
        watchlist_symbols = [item.ticker for item in watchlist_items]
        symbols_to_fetch = list(dict.fromkeys([*symbols, *watchlist_symbols]))

        created = 0
        for symbol in symbols_to_fetch:
            snapshot_data = fetch_with_fallback(symbol, week_id)
            stmt = insert(MarketDataSnapshot).values(
                report_id=report_uuid,
                provider=snapshot_data.provider,
                symbol=snapshot_data.symbol,
                payload=snapshot_data.payload,
                status=snapshot_data.status,
                cache_key=snapshot_data.cache_key,
            )
            # Idempotent: doppelte cache_keys werden ignoriert.
            stmt = stmt.on_conflict_do_nothing(index_elements=["cache_key"])
            result = await session.execute(stmt)
            if result.rowcount:
                created += int(result.rowcount)

        today = datetime.date.today()
        for item in watchlist_items:
            start_date = item.added_at.date() if item.added_at else today
            snapshot_data = finnhub.fetch_weekly_candles(
                item.ticker, start_date, today
            )
            stmt = insert(MarketDataSnapshot).values(
                report_id=report_uuid,
                provider=snapshot_data.provider,
                symbol=snapshot_data.symbol,
                payload=snapshot_data.payload,
                status=snapshot_data.status,
                cache_key=snapshot_data.cache_key,
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["cache_key"])
            result = await session.execute(stmt)
            if result.rowcount:
                created += int(result.rowcount)

        index_moves: list[IndexMove] = []
        for index_name, symbol in settings.market_index_symbols.items():
            snapshot_data = fetch_with_fallback(symbol, week_id)
            stmt = insert(MarketDataSnapshot).values(
                report_id=report_uuid,
                provider=snapshot_data.provider,
                symbol=snapshot_data.symbol,
                payload=snapshot_data.payload,
                status=snapshot_data.status,
                cache_key=snapshot_data.cache_key,
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["cache_key"])
            result = await session.execute(stmt)
            if result.rowcount:
                created += int(result.rowcount)

            payload = snapshot_data.payload
            if not isinstance(payload, dict):
                continue
            points_change = payload.get("d")
            percent_change = payload.get("dp")
            if points_change is None and percent_change is None:
                continue

            points_value = float(points_change) if isinstance(points_change, (int, float)) else None
            percent_value = float(percent_change) if isinstance(percent_change, (int, float)) else None
            direction = "flat"
            if points_value is not None and points_value != 0:
                direction = "up" if points_value > 0 else "down"
            elif percent_value is not None and percent_value != 0:
                direction = "up" if percent_value > 0 else "down"

            index_moves.append(
                IndexMove(
                    index=index_name,
                    percent_change=percent_value,
                    points_change=points_value,
                    direction=direction,
                )
            )

        extracted_inputs = report.extracted_inputs or {}
        market_context = extracted_inputs.get("market_context") or {}
        if isinstance(market_context, dict):
            market_context["index_moves"] = [move.model_dump() for move in index_moves]
            extracted_inputs["market_context"] = market_context
            report.extracted_inputs = extracted_inputs

        await session.commit()
        return created


def run_provider_fetch(report_id: str, week_id: str, symbols: list[str]) -> int:
    return asyncio.run(_fetch_and_store(report_id, week_id, symbols))
