import asyncio
import json

import jwt
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, WebSocket
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.security import decode_token, is_token_revoked
from app.data_access.database import get_db
from app.data_access.redis_client import get_redis
from app.modules.user.models import User
from app.realtime.connection_manager import manager
from app.modules.match.models.match import Match
from app.modules.tournament.models.tournament import Tournament
router = APIRouter(tags=["WebSocket"])


def authenticate_websocket_token(token: str, db: Session) -> User | None:
    """Validate an access token and return its active user."""
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "access":
        return None

    user_id_value = payload.get("sub")
    try:
        user_id = int(user_id_value)
        if user_id < 1:
            return None
    except (TypeError, ValueError):
        return None

    try:
        invalidated_after = get_redis().get(
            f"token_invalidated_after:{user_id}"
        )
    except Exception:
        return None

    if is_token_revoked(payload, invalidated_after):
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        return None

    return user


def _match_exists(db: Session, match_id: int, public_only: bool = False) -> bool:
    """Check a match exists, then release the session's connection.

    public_only limits anonymous viewers to matches of tournaments whose
    fixtures are published.
    """
    try:
        query = db.query(Match.id).filter(Match.id == match_id)
        if public_only:
            query = query.join(Tournament, Tournament.id == Match.tournament_id).filter(
                Tournament.fixtures_published.is_(True)
            )
        return query.first() is not None
    finally:
        db.rollback()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    """Accept authenticated WebSocket clients and handle heartbeats."""
    await websocket.accept()
    user_id: int | None = None
    anonymous = False

    try:
        try:
            raw_message = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=10,
            )
            message = json.loads(raw_message)
        except (
            asyncio.TimeoutError,
            json.JSONDecodeError,
            WebSocketDisconnect,
        ):
            await websocket.close(
                code=1008,
                reason="Authentication required",
            )
            return

        if not isinstance(message, dict) or message.get("type") != "auth":
            await websocket.close(
                code=1008,
                reason="Authentication required",
            )
            return

        token = message.get("token")

        # Visitors who are not signed in may watch public live scores. They
        # opt in explicitly and never receive personal notifications.
        if message.get("anonymous") is True and not token:
            anonymous = True
            manager.connect_anonymous(websocket)
            await websocket.send_json({
                "type": "auth:success",
                "payload": {"user_id": None, "role": "guest"},
            })
        elif not isinstance(token, str) or not token.strip():
            await websocket.close(
                code=1008,
                reason="Invalid authentication",
            )
            return

        if not anonymous:
            user = await run_in_threadpool(authenticate_websocket_token, token, db)
            user_role = user.role if user is not None else None
            authenticated_id = user.id if user is not None else None
            # End the read transaction so the pooled connection is returned: a
            # socket can stay open for hours and must not hold it meanwhile.
            db.rollback()
            if user is None:
                await websocket.close(
                    code=1008,
                    reason="Invalid authentication",
                )
                return

            user_id = authenticated_id
            await manager.connect(user_id, websocket)

            await websocket.send_json({
                "type": "auth:success",
                "payload": {
                    "user_id": user_id,
                    "role": user_role,
                },
            })


        while True:
            raw_message = await websocket.receive_text()

            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            if not isinstance(message, dict):
                continue

            message_type = message.get("type")

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if message_type not in {
                "subscribe_match",
                "unsubscribe_match",
            }:
                continue

            payload = message.get("payload")

            if not isinstance(payload, dict):
                await websocket.send_json({
                    "type": "error",
                    "payload": {"detail": "Invalid message payload"},
                })
                continue

            match_id = payload.get("match_id")

            if (
                isinstance(match_id, bool)
                or not isinstance(match_id, int)
                or match_id < 1
            ):
                await websocket.send_json({
                    "type": "error",
                    "payload": {"detail": "Invalid match_id"},
                })
                continue

            match_exists = await run_in_threadpool(
                _match_exists, db, match_id, anonymous
            )

            if not match_exists:
                await websocket.send_json({
                    "type": "error",
                    "payload": {"detail": "Match not found"},
                })
                continue

            if message_type == "subscribe_match":
                manager.subscribe_to_match(match_id, websocket)

                await websocket.send_json({
                    "type": "match:subscribed",
                    "payload": {"match_id": match_id},
                })
            else:
                manager.unsubscribe_from_match(match_id, websocket)

                await websocket.send_json({
                    "type": "match:unsubscribed",
                    "payload": {"match_id": match_id},
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011, reason="WebSocket error")
        except Exception:
            pass
    finally:
        if user_id is not None:
            manager.disconnect(user_id, websocket)
        if anonymous:
            manager.disconnect_anonymous(websocket)
