
import asyncio
import json

import fakeredis.aioredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.realtime.redis_pubsub import (
    REALTIME_EVENTS_CHANNEL,
    RedisPubSubManager,
)


@pytest.mark.anyio
async def test_publish_event_sends_json_to_subscriber():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = RedisPubSubManager(redis)
    pubsub = redis.pubsub()

    await pubsub.subscribe(REALTIME_EVENTS_CHANNEL)

    event = {
        "type": "match_status:update",
        "payload": {
            "match_id": 12,
            "status": "in_progress",
        },
    }

    try:
        for _ in range(50):
            subscribers = await redis.pubsub_numsub(
                REALTIME_EVENTS_CHANNEL
            )
            if subscribers and subscribers[0][1] > 0:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("Redis subscriber was not registered")

        result = await manager.publish_event(event)
        assert result is True

        for _ in range(50):
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=0.1,
            )

            if message is not None:
                assert message["type"] == "message"
                assert json.loads(message["data"]) == event
                break
        else:
            pytest.fail("Subscriber did not receive the published event")

    finally:
        await pubsub.aclose()
        await redis.aclose()


@pytest.mark.anyio
async def test_subscribe_receives_published_event():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = RedisPubSubManager(redis)
    received = []

    async def receive_one_event():
        async for event in manager.subscribe():
            received.append(event)
            break

    listener = asyncio.create_task(receive_one_event())

    expected = {
        "type": "live_score:update",
        "payload": {
            "match_id": 7,
            "score": {
                "team_a_score": 2,
                "team_b_score": 1,
            },
        },
    }

    try:
        for _ in range(50):
            subscribers = await redis.pubsub_numsub(
                REALTIME_EVENTS_CHANNEL
            )
            if subscribers and subscribers[0][1] > 0:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("Redis listener did not subscribe")

        await redis.publish(
            REALTIME_EVENTS_CHANNEL,
            json.dumps(expected),
        )

        await asyncio.wait_for(listener, timeout=2)

        assert received == [expected]

    finally:
        if not listener.done():
            listener.cancel()
            try:
                await listener
            except asyncio.CancelledError:
                pass

        await redis.aclose()


@pytest.mark.anyio
async def test_publish_event_rejects_invalid_event():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = RedisPubSubManager(redis)

    invalid_events = [
        {"type": "unsupported:event", "payload": {}},
        {
            "type": "match_status:update",
            "payload": {"match_id": 0},
        },
        {
            "type": "match_status:update",
            "payload": {"match_id": True},
        },
        {
            "type": "live_score:update",
            "payload": "not-an-object",
        },
        {
            "type": "notification:new",
            "payload": {"recipient_id": -1},
        },
        {
            "type": "notification:new",
            "payload": {"recipient_id": True},
        },
        {
            "type": "fixture:update",
            "payload": {"fixture_id": 0},
        },
    ]

    try:
        for event in invalid_events:
            assert await manager.publish_event(event) is False
    finally:
        await redis.aclose()


@pytest.mark.anyio
async def test_publish_event_handles_redis_failure():
    class FailingRedis:
        async def publish(self, channel, message):
            raise RedisConnectionError("Redis unavailable")

    manager = RedisPubSubManager(FailingRedis())

    result = await manager.publish_event(
        {
            "type": "match_status:update",
            "payload": {
                "match_id": 12,
                "status": "in_progress",
            },
        }
    )

    assert result is False


@pytest.mark.anyio
async def test_notification_event_is_valid():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = RedisPubSubManager(redis)

    event = {
        "type": "notification:new",
        "payload": {
            "recipient_id": 5,
            "notification_id": 19,
            "message": "Match starts soon",
        },
    }

    try:
        assert await manager.publish_event(event) is True
    finally:
        await redis.aclose()
