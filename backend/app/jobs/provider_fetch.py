from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.dialects.postgresql import insert

from app.db.models import MarketDataSnapshot, Report
from app.db.session import AsyncSessionLocal
from app.providers.selector import fetch_with_fallback


async def _fetch_and_store(report_id: str, week_id: str, symbols: list[str]) -> int:
    report_uuid = uuid.UUID(report_id)
    async with AsyncSessionLocal() as session:
        report = await session.get(Report, report_uuid)
        if report is None:
            return 0

        created = 0
        for symbol in dict.fromkeys(symbols):
            snapshot_data = fetch_with_fallback(symbol, week_id)
            stmt = insert(MarketDataSnapshot).values(
                report_id=report_uuid,
                provider=snapshot_data.provider,
                symbol=snapshot_data.symbol,
                payload=snapshot_data.payload,
                cache_key=snapshot_data.cache_key,
            )
            # Idempotent: doppelte cache_keys werden ignoriert.
            stmt = stmt.on_conflict_do_nothing(index_elements=["cache_key"])
            result = await session.execute(stmt)
            if result.rowcount:
                created += int(result.rowcount)

        await session.commit()
        return created


def run_provider_fetch(report_id: str, week_id: str, symbols: list[str]) -> int:
    return asyncio.run(_fetch_and_store(report_id, week_id, symbols))
