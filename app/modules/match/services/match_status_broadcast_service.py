
from app.modules.match.models.match import Match
from app.realtime.redis_pubsub import pubsub_manager


async def broadcast_match_status(match: Match) -> None:
    """Publish match status changes through Redis."""
    await pubsub_manager.publish_event(
        {
            "type": "match_status:update",
            "payload": {
                "match_id": match.id,
                "status": match.status,
            },
        }
    )
