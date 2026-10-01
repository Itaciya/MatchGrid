import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.user.models import User

client = TestClient(app)


def _make_user(db, **overrides):
    defaults = dict(
        email=f"logout_test_{uuid4()}@example.com",
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


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_logout_succeeds_with_valid_token(db):
    user = _make_user(db)
    token = create_access_token(user.id, user.role)

    response = client.post("/auth/logout", headers=_auth_header(token))
    assert response.status_code == 204


def test_logout_without_token_is_rejected():
    response = client.post("/auth/logout")
    assert response.status_code == 401  # HTTPBearer's missing-credentials code


def test_token_rejected_after_logout(db):
    user = _make_user(db)
    token = create_access_token(user.id, user.role)

    logout_response = client.post("/auth/logout", headers=_auth_header(token))
    assert logout_response.status_code == 204

    me_response = client.get("/auth/me", headers=_auth_header(token))
    assert me_response.status_code == 401


def test_new_login_after_logout_still_works(db):
    user = _make_user(db)
    old_token = create_access_token(user.id, user.role)
    client.post("/auth/logout", headers=_auth_header(old_token))

    time.sleep(1)  # ensure new token's iat differs from the invalidation cutoff second

    new_token = create_access_token(user.id, user.role)
    response = client.get("/auth/me", headers=_auth_header(new_token))
    assert response.status_code == 200


def test_refresh_token_removed_after_logout(db, fake_redis):
    user = _make_user(db)
    token = create_access_token(user.id, user.role)

    fake_redis.set(f"refresh_token:{user.id}", "some-jti", ex=600)
    client.post("/auth/logout", headers=_auth_header(token))

    assert fake_redis.get(f"refresh_token:{user.id}") is None
