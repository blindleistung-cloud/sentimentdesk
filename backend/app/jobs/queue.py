from __future__ import annotations

from redis import Redis
from rq import Queue
from rq.job import Job

from app.config.settings import settings
from app.jobs.provider_fetch import run_provider_fetch


def get_redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url)


def get_queue(name: str | None = None) -> Queue:
    queue_name = name or settings.provider_queue_name
    return Queue(name=queue_name, connection=get_redis_connection())


def enqueue_provider_fetch(report_id: str, week_id: str, symbols: list[str]) -> Job:
    queue = get_queue()
    return queue.enqueue(run_provider_fetch, report_id=report_id, week_id=week_id, symbols=symbols)
