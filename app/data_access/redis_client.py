from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


redis_client = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    health_check_interval=30,
)


def get_redis() -> Redis:
    """Return the reusable Redis client."""
    return redis_client


def test_redis_connection() -> str:
    """Test Redis connectivity and return a readable status."""
    try:
        redis_client.ping()
        return "Redis connection successful"

    except RedisError as exc:
        return f"Redis connection failed: {exc}"