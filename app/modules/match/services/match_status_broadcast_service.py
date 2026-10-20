from app.modules.match.models.match import Match
from app.realtime.connection_manager import manager


async def broadcast_match_status(match: Match) -> None:
    """Broadcast a persisted match status to clients subscribed to that match."""
    await manager.broadcast_to_match(
        match.id,
        {
            "type": "match_status:update",
            "payload": {
                "match_id": match.id,
                "status": match.status,
            },
        },
    )
