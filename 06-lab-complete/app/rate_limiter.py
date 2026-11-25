"""Sliding window 60 giây, cập nhật nguyên tử trong Redis."""

import hashlib
import math
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


_RATE_LIMIT_SCRIPT = """
local bucket = KEYS[1]
local now = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local member = ARGV[3]
local window = 60000
redis.call('ZREMRANGEBYSCORE', bucket, '-inf', now - window)
if redis.call('ZCARD', bucket) >= limit then
    local oldest = redis.call('ZRANGE', bucket, 0, 0, 'WITHSCORES')
    local retry_ms = 60000
    if oldest[2] then
        retry_ms = math.max(1, tonumber(oldest[2]) + window - now)
    end
    return {0, retry_ms}
end
redis.call('ZADD', bucket, now, member)
redis.call('PEXPIRE', bucket, window)
return {1, 0}
"""


def check_rate_limit(key: str) -> None:
    # Không để lộ API key trong tên Redis key.
    bucket = "rate:" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    now_ms = int(time.time() * 1000)
    try:
        allowed, retry_ms = r.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            bucket,
            now_ms,
            settings.rate_limit_per_minute,
            uuid.uuid4().hex,
        )
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limit store unavailable") from exc

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, math.ceil(retry_ms / 1000)))},
        )
