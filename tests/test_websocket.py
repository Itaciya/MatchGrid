from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.user.models import User
from app.realtime.connection_manager import manager

client = TestClient(app)


def _make_user(db, **overrides):
    defaults = dict(
        email=f"websocket_test_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role="player",
        is_active=True,
    )
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _authenticate(websocket, user):
    token = create_access_token(user.id, user.role)
    websocket.send_json({"type": "auth", "token": token})
    return websocket.receive_json()


def test_websocket_accepts_valid_access_token(db, monkeypatch, fake_redis):
    monkeypatch.setattr(
        "app.realtime.routes.get_redis",
        lambda: fake_redis,
    )
    user = _make_user(db)

    with client.websocket_connect("/ws") as websocket:
        response = _authenticate(websocket, user)

        assert response["type"] == "auth:success"
        assert response["payload"]["user_id"] == user.id
        assert response["payload"]["role"] == user.role
        assert len(manager.active_connections[user.id]) == 1
    assert user.id not in manager.active_connections


def test_websocket_rejects_invalid_token(monkeypatch, fake_redis):
    monkeypatch.setattr(
        "app.realtime.routes.get_redis",
        lambda: fake_redis,
    )

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "type": "auth",
                "token": "not-a-valid-token",
            })
            websocket.receive_json()


def test_websocket_rejects_wrong_auth_message():
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"type": "ping"})
            websocket.receive_json()


def test_websocket_responds_to_ping(db, monkeypatch, fake_redis):
    monkeypatch.setattr(
        "app.realtime.routes.get_redis",
        lambda: fake_redis,
    )
    user = _make_user(db)

    with client.websocket_connect("/ws") as websocket:
        response = _authenticate(websocket, user)
        assert response["type"] == "auth:success"

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}
