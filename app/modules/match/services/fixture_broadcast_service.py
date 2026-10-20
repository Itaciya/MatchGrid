
from app.modules.match.models.match import Match
from app.realtime.redis_pubsub import pubsub_manager


async def broadcast_fixture_update(match: Match) -> None:
    """Publish fixture changes for WebSocket subscribers across instances."""
    await pubsub_manager.publish_event(
        {
            "type": "fixture:update",
            "payload": {
                "match_id": match.id,
                "fixture_id": match.id,
                "scheduled_at": (
                    match.scheduled_at.isoformat()
                    if match.scheduled_at is not None
                    else None
                ),
                "venue_id": match.venue_id,
                "status": match.status,
            },
        }
    )
