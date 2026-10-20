from app.modules.match.models.match import Match
from app.realtime.connection_manager import manager


async def broadcast_fixture_update(match: Match) -> None:
    """Broadcast updated fixture details to clients subscribed to the match."""

    await manager.broadcast_to_match(
        match.id,
        {
            "type": "fixture:update",
            "payload": {
                "fixture_id": match.id,
                "scheduled_at": (
                    match.scheduled_at.isoformat()
                    if match.scheduled_at is not None
                    else None
                ),
                "venue_id": match.venue_id,
                "status": match.status,
            },
        },
    )