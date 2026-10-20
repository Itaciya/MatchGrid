
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.realtime.connection_manager import manager as connection_manager

logger = logging.getLogger(__name__)

REALTIME_EVENTS_CHANNEL = "matchgrid:realtime:events"

SUPPORTED_EVENT_TYPES = {
    "live_score:update",
    "match_status:update",
    "fixture:update",
    "notification:new",
}


class RedisPubSubManager:
    """Publish validated events and forward Redis events to local WebSocket clients."""

    def __init__(self, redis: Redis | None = None) -> None:
        self._owns_client = redis is None
        self.redis = redis if redis is not None else self._create_redis_client()
        self.event_loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    @staticmethod
    def _create_redis_client() -> Redis:
        """Create an asynchronous Redis client using application settings."""
        return Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )

    async def _ensure_open(self) -> None:
        """Recreate an owned Redis client if a previous app lifespan closed it."""
        if self._closed and self._owns_client:
            self.redis = self._create_redis_client()
            self._closed = False

    @staticmethod
    def validate_event(event: dict[str, Any]) -> bool:
        """Validate event type and its required routing identifier."""
        if not isinstance(event, dict):
            return False

        event_type = event.get("type")
        payload = event.get("payload")

        if event_type not in SUPPORTED_EVENT_TYPES:
            return False

        if not isinstance(payload, dict):
            return False

        if event_type == "notification:new":
            recipient_id = payload.get("recipient_id")
            return (
                isinstance(recipient_id, int)
                and not isinstance(recipient_id, bool)
                and recipient_id > 0
            )

        match_id = payload.get("match_id")

        if event_type == "fixture:update" and match_id is None:
            match_id = payload.get("fixture_id")

        return (
            isinstance(match_id, int)
            and not isinstance(match_id, bool)
            and match_id > 0
        )

    async def publish_event(
        self,
        event: dict[str, Any],
        channel: str = REALTIME_EVENTS_CHANNEL,
    ) -> bool:
        """Publish a valid event; return False if validation or Redis fails."""
        if not self.validate_event(event):
            logger.warning("Rejected invalid real-time event")
            return False

        try:
            await self._ensure_open()
            encoded_event = json.dumps(event)
            await self.redis.publish(channel, encoded_event)
            return True
        except (RedisError, TypeError, ValueError, RuntimeError):
            logger.exception("Failed to publish a real-time event")
            return False

    def schedule_event(
        self,
        event: dict[str, Any],
        channel: str = REALTIME_EVENTS_CHANNEL,
    ) -> bool:
        """
        Schedule publishing from a synchronous background thread.

        The event loop is recorded when listen_for_events() starts.
        """
        if not self.validate_event(event):
            logger.warning("Rejected invalid scheduled real-time event")
            return False

        loop = self.event_loop

        if loop is None or loop.is_closed() or self._closed:
            logger.warning(
                "Cannot schedule real-time event: event loop is unavailable"
            )
            return False

        async def publish_safely() -> None:
            await self.publish_event(event, channel)

        def schedule_publish() -> None:
            if loop.is_closed():
                return

            task = loop.create_task(publish_safely())
            task.add_done_callback(self._log_scheduled_task_error)

        try:
            loop.call_soon_threadsafe(schedule_publish)
            return True
        except RuntimeError:
            logger.exception("Could not schedule real-time event")
            return False

    @staticmethod
    def _log_scheduled_task_error(task: asyncio.Task) -> None:
        """Log unexpected errors from scheduled publishing tasks."""
        if task.cancelled():
            return

        try:
            task.result()
        except Exception:
            logger.exception("Scheduled real-time event publishing failed")

    async def subscribe(
        self,
        channel: str = REALTIME_EVENTS_CHANNEL,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield validated JSON events from a Redis Pub/Sub channel."""
        await self._ensure_open()
        pubsub = self.redis.pubsub()

        try:
            await pubsub.subscribe(channel)

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue

                try:
                    event = json.loads(message["data"])
                except (TypeError, ValueError, KeyError):
                    logger.warning(
                        "Ignoring invalid JSON on Redis channel %s",
                        channel,
                    )
                    continue

                if not isinstance(event, dict) or not self.validate_event(event):
                    logger.warning(
                        "Ignoring invalid event on Redis channel %s",
                        channel,
                    )
                    continue

                yield event

        except asyncio.CancelledError:
            raise
        except RedisError:
            logger.exception(
                "Redis subscription failed for channel %s",
                channel,
            )
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except RedisError:
                logger.warning(
                    "Could not unsubscribe from Redis channel %s",
                    channel,
                    exc_info=True,
                )
            finally:
                await pubsub.aclose()

    async def listen_for_events(self) -> None:
        """Receive Redis events and forward them to local WebSocket clients."""
        self.event_loop = asyncio.get_running_loop()

        while True:
            try:
                async for event in self.subscribe():
                    event_type = event["type"]
                    payload = event["payload"]

                    if event_type == "notification:new":
                        await connection_manager.send_personal_message(
                            event,
                            payload["recipient_id"],
                        )
                        continue

                    match_id = payload.get("match_id")

                    if event_type == "fixture:update" and match_id is None:
                        match_id = payload["fixture_id"]

                    await connection_manager.broadcast_to_match(
                        match_id,
                        event,
                    )

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected Redis listener error")

            # Retry after Redis errors or an unexpectedly ended subscription.
            await asyncio.sleep(1)

    async def close(self) -> None:
        """Close an owned Redis client and allow later lifespan restarts."""
        self.event_loop = None

        if self._owns_client and not self._closed:
            await self.redis.aclose()
            self._closed = True


# Shared instance: use this instance for both publishing and listening.
pubsub_manager = RedisPubSubManager()
