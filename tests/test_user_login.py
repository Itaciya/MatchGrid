from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import decode_token, hash_password
from app.main import app
from app.modules.user.models import User

client = TestClient(app)


def _make_user(db, **overrides):
    defaults = dict(
        email=f"login_test_{uuid4()}@example.com",
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


def test_login_with_valid_credentials_succeeds(db, fake_redis):
    user = _make_user(db)

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": "correctpassword123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_wrong_password_is_rejected(db, fake_redis):
    user = _make_user(db)

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"


def test_login_with_unknown_email_is_rejected(fake_redis):
    response = client.post(
        "/auth/login",
        json={"email": "doesnotexist@example.com", "password": "whatever123"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"


def test_login_with_inactive_user_is_rejected(db, fake_redis):
    user = _make_user(db, is_active=False)

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": "correctpassword123"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Account is inactive"


def test_successful_login_stores_refresh_token_jti_in_redis(db, fake_redis):
    user = _make_user(db)

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": "correctpassword123"},
    )

    assert response.status_code == 200
    stored = fake_redis.get(f"refresh_token:{user.id}")
    assert stored is not None


def test_access_token_contains_expected_claims(db, fake_redis):
    user = _make_user(db)

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": "correctpassword123"},
    )

    payload = decode_token(response.json()["access_token"])
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "player"
    assert payload["type"] == "access"
