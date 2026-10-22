
import logging
from dataclasses import dataclass

from redis.exceptions import RedisError

from app.core.config import settings
from app.data_access.redis_client import get_redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


def check_rate_limit(
    client_key: str,
    *,
    authenticated: bool,
) -> RateLimitResult:
    """Atomically count requests in a fixed Redis time window."""
    limit = (
        settings.RATE_LIMIT_AUTHENTICATED_REQUESTS
        if authenticated
        else settings.RATE_LIMIT_PUBLIC_REQUESTS
    )
    window = settings.RATE_LIMIT_WINDOW_SECONDS

    if limit < 1 or window < 1:
        raise ValueError("Rate limit and window must be positive")

    key = f"matchgrid:rate-limit:{window}:{client_key}"

    try:
        redis_client = get_redis()

        # Atomically increment the counter and set its expiry.
        count, ttl = redis_client.eval(
            """
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            local ttl = redis.call('TTL', KEYS[1])
            return {count, ttl}
            """,
            1,
            key,
            window,
        )
    except RedisError:
        logger.exception("Redis rate-limit check failed")
        # Fail open if Redis is unavailable.
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit,
            retry_after=0,
        )

    count = int(count)
    ttl = max(1, int(ttl))

    return RateLimitResult(
        allowed=count <= limit,
        limit=limit,
        remaining=max(0, limit - count),
        retry_after=ttl if count > limit else 0,
    )
