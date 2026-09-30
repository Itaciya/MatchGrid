from uuid import uuid4

from fastapi import Depends
from fastapi.testclient import TestClient

from app.core.dependencies import require_role
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.user.models import User

client = TestClient(app)


# A throwaway role-gated route, added only for this test module, so we can
# exercise require_role() without depending on SCRUM-54's real endpoints.
@app.get("/auth/_test-organiser-only")
def _organiser_only_route(current_user: User = Depends(require_role("organiser"))):
    return {"ok": True}


def _make_user(db, **overrides):
    defaults = dict(
        email=f"protected_test_{uuid4()}@example.com",
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


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_me_without_token_is_rejected():
    response = client.get("/auth/me")
    assert response.status_code == 401  # no credentials = unauthenticated, not forbidden


def test_me_with_garbage_token_is_rejected():
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_me_with_valid_token_succeeds(db):
    user = _make_user(db)
    response = client.get("/auth/me", headers=_auth_header(user))

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_me_with_inactive_user_token_is_rejected(db):
    user = _make_user(db, is_active=False)
    response = client.get("/auth/me", headers=_auth_header(user))

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Account is inactive"


def test_role_gated_route_allows_matching_role(db):
    user = _make_user(db, role="organiser")
    response = client.get("/auth/_test-organiser-only", headers=_auth_header(user))
    assert response.status_code == 200


def test_role_gated_route_denies_other_roles(db):
    user = _make_user(db, role="player")
    response = client.get("/auth/_test-organiser-only", headers=_auth_header(user))
    assert response.status_code == 403

