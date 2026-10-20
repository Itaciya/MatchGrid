
import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manage authenticated WebSocket connections and match subscriptions."""

    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = {}
        self.match_connections: dict[int, set[WebSocket]] = {}
        self.event_loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """Register a WebSocket for an authenticated user."""
        self.event_loop = asyncio.get_running_loop()
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket and its match subscriptions."""
        connections = self.active_connections.get(user_id)

        if connections is not None:
            connections.discard(websocket)
            if not connections:
                self.active_connections.pop(user_id, None)

        for match_id, subscribers in list(self.match_connections.items()):
            subscribers.discard(websocket)
            if not subscribers:
                self.match_connections.pop(match_id, None)

    def subscribe_to_match(
        self,
        match_id: int,
        websocket: WebSocket,
    ) -> None:
        """Subscribe a connected WebSocket to one match's live updates."""
        if match_id < 1:
            raise ValueError("match_id must be a positive integer")

        if not any(
            websocket in connections
            for connections in self.active_connections.values()
        ):
            raise ValueError("WebSocket must connect before subscribing")

        self.match_connections.setdefault(match_id, set()).add(websocket)

    def unsubscribe_from_match(
        self,
        match_id: int,
        websocket: WebSocket,
    ) -> None:
        """Unsubscribe a WebSocket from one match."""
        subscribers = self.match_connections.get(match_id)
        if subscribers is None:
            return

        subscribers.discard(websocket)
        if not subscribers:
            self.match_connections.pop(match_id, None)

    def schedule_personal_message(
        self,
        message: dict[str, Any],
        user_id: int,
    ) -> bool:
        """Schedule a private message from another thread."""
        loop = self.event_loop

        if loop is None or loop.is_closed():
            return False

        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(
                self.send_personal_message(message, user_id)
            )
        )
        return True

    async def send_personal_message(
        self,
        message: dict[str, Any],
        user_id: int,
    ) -> None:
        """Send a message to every active connection for one user."""
        connections = self.active_connections.get(user_id, set())

        for websocket in list(connections):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(user_id, websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected authenticated users."""
        for user_id, connections in list(self.active_connections.items()):
            for websocket in list(connections):
                try:
                    await websocket.send_json(message)
                except Exception:
                    self.disconnect(user_id, websocket)

    async def broadcast_to_match(
        self,
        match_id: int,
        message: dict[str, Any],
    ) -> None:
        """Send a message only to clients subscribed to the specified match."""
        subscribers = self.match_connections.get(match_id, set())

        for websocket in list(subscribers):
            try:
                await websocket.send_json(message)
            except Exception:
                for user_id, connections in list(
                    self.active_connections.items()
                ):
                    if websocket in connections:
                        self.disconnect(user_id, websocket)
                        break


manager = ConnectionManager()
