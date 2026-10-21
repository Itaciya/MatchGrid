from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from app.main import app
from app.modules.user.models import User

client = TestClient(app)

WRONG_KEY = "a-completely-different-signing-key-0123456789"


def _make_user(db, role="player"):
    user = User(
        email=f"jwt_test_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _claims(user_id, role="player", expires_in=timedelta(minutes=15)):
    now = datetime.now(timezone.utc)
    return {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires_in,
    }


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# SCRUM-240: JWT generation

def test_access_token_has_expected_claims_and_lifetime():
    claims = decode_token(create_access_token(42, "organiser"))

    assert claims["sub"] == "42"
    assert claims["role"] == "organiser"
    assert claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_refresh_token_has_type_subject_and_jti():
    token, jti = create_refresh_token(42)
    claims = decode_token(token)

    assert claims["type"] == "refresh"
    assert claims["sub"] == "42"
    assert claims["jti"] == jti
    assert claims["exp"] > datetime.now(timezone.utc).timestamp()


def test_each_refresh_token_gets_a_unique_jti():
    first_token, first_jti = create_refresh_token(1)
    second_token, second_jti = create_refresh_token(1)

    assert first_jti != second_jti
    assert first_token != second_token


# SCRUM-240: decoding rejects bad tokens

def test_decode_rejects_expired_token():
    token = jwt.encode(
        _claims(1, expires_in=timedelta(seconds=-5)),
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_decode_rejects_token_signed_with_another_key():
    token = jwt.encode(_claims(1), WRONG_KEY, algorithm=ALGORITHM)

    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(token)


def test_decode_rejects_unsigned_token():
    token = jwt.encode(_claims(1), key=None, algorithm="none")

    with pytest.raises(jwt.PyJWTError):
        decode_token(token)


def test_decode_rejects_garbage():
    with pytest.raises(jwt.PyJWTError):
        decode_token("not.a.jwt")


# SCRUM-240: protected endpoints

def test_valid_token_grants_access(db):
    user = _make_user(db)

    response = client.get("/auth/me", headers=_bearer(create_access_token(user.id, user.role)))

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_expired_token_is_rejected(db):
    user = _make_user(db)
    token = jwt.encode(
        _claims(user.id, user.role, expires_in=timedelta(seconds=-5)),
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_token_signed_with_another_key_is_rejected(db):
    user = _make_user(db)
    token = jwt.encode(_claims(user.id, user.role), WRONG_KEY, algorithm=ALGORITHM)

    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_unsigned_token_is_rejected(db):
    user = _make_user(db)
    token = jwt.encode(_claims(user.id, user.role), key=None, algorithm="none")

    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_token_for_a_user_that_does_not_exist_is_rejected():
    token = create_access_token(2_000_000_000, "player")

    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_refresh_token_cannot_be_used_as_an_access_token(db):
    user = _make_user(db)
    refresh_token, _ = create_refresh_token(user.id)

    assert client.get("/auth/me", headers=_bearer(refresh_token)).status_code == 401


def test_role_claim_in_a_token_does_not_grant_organiser_access(db):
    player = _make_user(db, role="player")
    forged = create_access_token(player.id, "organiser")

    response = client.get("/disputes/pending", headers=_bearer(forged))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "header", ["Bearer", "Bearer ", "Basic abc123", "just-a-token", ""]
)
def test_malformed_authorization_headers_are_rejected(header):
    response = client.get("/auth/me", headers={"Authorization": header})

    assert response.status_code in (401, 403)


@pytest.mark.parametrize(
    "path",
    [
        "/auth/me",
        "/notifications/",
        "/disputes/pending",
        "/official-assignments/my-matches",
        "/matches/1/score",
    ],
)
def test_protected_endpoints_require_authentication(path):
    assert client.get(path).status_code in (401, 403)