from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, hash_password
from app.data_access.database import get_db
from app.main import app
from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.realtime.connection_manager import manager


client = TestClient(app)


@pytest.fixture
def websocket_db_override(db):
    """Use the test database session for WebSocket requests."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def cleanup_websocket_manager():
    """Prevent WebSocket connections from leaking between tests."""
    yield

    manager.active_connections.clear()

    # Clear match subscriptions if this manager supports them.
    subscriptions = getattr(manager, "match_subscriptions", None)
    if subscriptions is not None:
        subscriptions.clear()


def _make_user(db, **overrides):
    defaults = {
        "email": f"websocket_test_{uuid4()}@example.com",
        "password_hash": hash_password("correctpassword123"),
        "role": "player",
        "is_active": True,
    }
    defaults.update(overrides)

    user = User(**defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"WebSocket Tournament {uuid4()}",
        description="WebSocket test tournament",
        format="knockout",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
        registration_open_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
        registration_close_at=datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc),
    )
    db.add(tournament)
    db.flush()
    return tournament


def _make_match(db, tournament_id, captain_id):
    teams = []

    for _ in range(2):
        team = Team(
            name=f"WebSocket Team {uuid4()}",
            captain_id=captain_id,
        )
        db.add(team)
        db.flush()
        teams.append(team)

    match = Match(
        tournament_id=tournament_id,
        match_number=1,
        team_a_id=teams[0].id,
        team_b_id=teams[1].id,
        scheduled_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db.add(match)
    db.flush()
    return match


def _patch_redis(monkeypatch, fake_redis):
    monkeypatch.setattr(
        "app.realtime.routes.get_redis",
        lambda: fake_redis,
    )


def _authenticate(websocket, user):
    token = create_access_token(user.id, user.role)
    websocket.send_json({"type": "auth", "token": token})
    return websocket.receive_json()


def test_websocket_accepts_valid_access_token(
    db, monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)
    user = _make_user(db)

    with client.websocket_connect("/ws") as websocket:
        response = _authenticate(websocket, user)

        assert response["type"] == "auth:success"
        assert response["payload"]["user_id"] == user.id
        assert response["payload"]["role"] == user.role
        assert len(manager.active_connections[user.id]) == 1

    assert user.id not in manager.active_connections


def test_websocket_rejects_invalid_token(
    monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "type": "auth",
                "token": "not-a-valid-token",
            })
            websocket.receive_json()


def test_websocket_rejects_wrong_auth_message(websocket_db_override):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"type": "ping"})
            websocket.receive_json()


def test_websocket_responds_to_ping(
    db, monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)
    user = _make_user(db)

    with client.websocket_connect("/ws") as websocket:
        response = _authenticate(websocket, user)
        assert response["type"] == "auth:success"

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}


def test_websocket_subscribes_to_match(
    db, monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)
    user = _make_user(db)
    tournament = _make_tournament(db, user.id)
    match = _make_match(db, tournament.id, user.id)

    with client.websocket_connect("/ws") as websocket:
        response = _authenticate(websocket, user)
        assert response["type"] == "auth:success"

        websocket.send_json({
            "type": "subscribe_match",
            "payload": {"match_id": match.id},
        })

        assert websocket.receive_json() == {
            "type": "match:subscribed",
            "payload": {"match_id": match.id},
        }

        assert len(manager.match_connections[match.id]) == 1

def test_websocket_unsubscribes_from_match(
    db, monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)
    user = _make_user(db)
    tournament = _make_tournament(db, user.id)
    match = _make_match(db, tournament.id, user.id)

    with client.websocket_connect("/ws") as websocket:
        response = _authenticate(websocket, user)
        assert response["type"] == "auth:success"

        websocket.send_json({
            "type": "subscribe_match",
            "payload": {"match_id": match.id},
        })
        assert websocket.receive_json()["type"] == "match:subscribed"

        websocket.send_json({
            "type": "unsubscribe_match",
            "payload": {"match_id": match.id},
        })

        assert websocket.receive_json() == {
            "type": "match:unsubscribed",
            "payload": {"match_id": match.id},
        }

        assert (
            match.id not in manager.match_connections
            or websocket not in manager.match_connections[match.id]
        )


def test_websocket_returns_error_for_invalid_match_id(
    db, monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)
    user = _make_user(db)

    with client.websocket_connect("/ws") as websocket:
        assert _authenticate(websocket, user)["type"] == "auth:success"

        websocket.send_json({
            "type": "subscribe_match",
            "payload": {"match_id": 0},
        })

        assert websocket.receive_json() == {
            "type": "error",
            "payload": {"detail": "Invalid match_id"},
        }


def test_websocket_returns_error_for_missing_match(
    db, monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)
    user = _make_user(db)

    with client.websocket_connect("/ws") as websocket:
        assert _authenticate(websocket, user)["type"] == "auth:success"

        websocket.send_json({
            "type": "subscribe_match",
            "payload": {"match_id": 999999999},
        })

        assert websocket.receive_json() == {
            "type": "error",
            "payload": {"detail": "Match not found"},
        }


def test_websocket_returns_error_for_invalid_payload(
    db, monkeypatch, fake_redis, websocket_db_override
):
    _patch_redis(monkeypatch, fake_redis)
    user = _make_user(db)

    with client.websocket_connect("/ws") as websocket:
        assert _authenticate(websocket, user)["type"] == "auth:success"

        websocket.send_json({
            "type": "subscribe_match",
            "payload": "invalid",
        })

        assert websocket.receive_json() == {
            "type": "error",
            "payload": {"detail": "Invalid message payload"},
        }
