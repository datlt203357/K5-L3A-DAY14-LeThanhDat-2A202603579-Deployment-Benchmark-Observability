"""Theo dõi ngân sách LLM theo ngày bằng Redis."""

from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_key() -> str:
    return "cost:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_budget() -> None:
    try:
        spent = float(r.get(_budget_key()) or 0)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost store unavailable") from exc
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily LLM budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (
        input_tokens * PRICE_INPUT_PER_1K / 1000
        + output_tokens * PRICE_OUTPUT_PER_1K / 1000
    )
    try:
        with r.pipeline() as pipe:
            pipe.incrbyfloat(_budget_key(), cost)
            pipe.expire(_budget_key(), 2 * 24 * 60 * 60)
            pipe.execute()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost store unavailable") from exc
    return cost
