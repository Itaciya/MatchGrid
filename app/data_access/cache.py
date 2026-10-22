import json
import logging
from typing import Any

from redis.exceptions import RedisError

from app.data_access.redis_client import get_redis

logger = logging.getLogger(__name__)


def get_cached_json(key: str) -> Any | None:
    """Return cached JSON data, or None when unavailable."""
    try:
        value = get_redis().get(key)
        if value is None:
            return None
        return json.loads(value)
    except (RedisError, ValueError, TypeError):
        logger.warning("Redis cache read failed for key %s", key)
        return None


def set_cached_json(
    key: str,
    value: Any,
    ttl_seconds: int = 60,
) -> None:
    """Cache JSON-serializable data for a limited time."""
    try:
        get_redis().set(key, json.dumps(value), ex=ttl_seconds)
    except (RedisError, ValueError, TypeError):
        logger.warning("Redis cache write failed for key %s", key)


def delete_cached_keys(*keys: str) -> None:
    """Invalidate cache keys after related data changes."""
    if not keys:
        return

    try:
        get_redis().delete(*keys)
    except RedisError:
        logger.warning("Redis cache invalidation failed")