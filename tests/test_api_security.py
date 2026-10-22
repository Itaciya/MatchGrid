
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.modules.user.models import User


client = TestClient(app)


def _make_user(
    db,
    *,
    role="organiser",
    email=None,
):
    if email is None:
        email = f"security-{uuid4().hex}@example.com"

    user = User(
        email=email,
        password_hash="not-used-for-token-tests",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_current_user_endpoint_rejects_missing_token():
    response = client.get("/auth/me")

    assert response.status_code in (401, 403)


def test_current_user_endpoint_rejects_malformed_token():
    response = client.get(
        "/auth/me",
        headers=_auth_header("this-is-not-a-valid-token"),
    )

    assert response.status_code == 401


def test_logout_endpoint_rejects_missing_token():
    response = client.post("/auth/logout")

    assert response.status_code in (401, 403)


def test_create_venue_rejects_missing_token():
    response = client.post(
        "/venues/",
        json={
            "name": "Security Test Venue",
            "location": "Test Location",
            "description": "Security test",
            "capacity": 100,
        },
    )

    assert response.status_code in (401, 403)


def test_update_venue_rejects_missing_token():
    response = client.patch(
        "/venues/999999",
        json={"name": "Updated Venue"},
    )

    assert response.status_code in (401, 403)


def test_delete_venue_rejects_missing_token():
    response = client.delete("/venues/999999")

    assert response.status_code in (401, 403)


def test_public_venue_list_does_not_require_authentication():
    response = client.get("/venues/")

    assert response.status_code == 200


def test_audit_logs_reject_missing_token():
    response = client.get("/audit-logs")

    assert response.status_code in (401, 403)


def test_audit_logs_reject_non_admin_user(db):
    user = _make_user(db, role="organiser")

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.get("/audit-logs")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
