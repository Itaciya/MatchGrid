from uuid import uuid4

import pytest
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


# SCRUM-240: validation, secrecy and token contents

@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "someone@example.com"},
        {"password": "correctpassword123"},
        {"email": "", "password": ""},
    ],
)
def test_login_with_missing_or_empty_fields_is_rejected(payload):
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 422


def test_login_failures_do_not_reveal_whether_the_email_exists(db, fake_redis):
    user = _make_user(db)

    wrong_password = client.post(
        "/auth/login", json={"email": user.email, "password": "wrongpassword"}
    )
    unknown_email = client.post(
        "/auth/login",
        json={"email": "nobody-here@example.com", "password": "wrongpassword"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_failed_login_does_not_echo_the_password(db, fake_redis):
    user = _make_user(db)

    response = client.post(
        "/auth/login", json={"email": user.email, "password": "wrongpassword"}
    )

    assert "wrongpassword" not in response.text


def test_login_response_does_not_expose_password_or_hash(db, fake_redis):
    user = _make_user(db)

    response = client.post(
        "/auth/login", json={"email": user.email, "password": "correctpassword123"}
    )

    assert response.status_code == 200
    assert "correctpassword123" not in response.text
    assert "password_hash" not in response.text


def test_login_access_token_grants_access_to_the_user(db, fake_redis):
    user = _make_user(db)
    login = client.post(
        "/auth/login", json={"email": user.email, "password": "correctpassword123"}
    )

    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )

    assert me.status_code == 200
    assert me.json()["email"] == user.email


def test_login_tokens_identify_the_user_and_their_type(db, fake_redis):
    user = _make_user(db, role="scorer")
    data = client.post(
        "/auth/login", json={"email": user.email, "password": "correctpassword123"}
    ).json()

    access = decode_token(data["access_token"])
    refresh = decode_token(data["refresh_token"])

    assert access["sub"] == str(user.id)
    assert access["role"] == "scorer"
    assert access["type"] == "access"
    assert refresh["sub"] == str(user.id)
    assert refresh["type"] == "refresh"