from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.user.models import User

client = TestClient(app)

ROLES = ["organiser", "player", "scorer", "spectator", "official", "captain"]
MISSING = 999999999

# (method, path, roles allowed). The role check runs before any database
# lookup or body validation, so a wrong role gets 403 and an allowed role gets
# some other answer (404 or 422 here), never 401 or 403.
ROLE_GATED = [
    ("POST", "/player-team/profile", {"player"}),
    ("PATCH", f"/player-team/profile/{MISSING}", {"player"}),
    ("PATCH", f"/player-team/profile/{MISSING}/status", {"organiser"}),
    ("POST", "/player-team/team", {"organiser"}),
    ("POST", "/registrations/", {"captain"}),
    ("POST", "/registrations/player", {"player"}),
    ("GET", f"/registrations/pending/{MISSING}", {"organiser"}),
    ("PATCH", f"/registrations/{MISSING}/approve", {"organiser"}),
    ("PATCH", f"/registrations/{MISSING}/reject", {"organiser"}),
    ("PATCH", f"/registrations/{MISSING}/status", {"organiser"}),
]

CASES = [
    (method, path, role, role in allowed)
    for method, path, allowed in ROLE_GATED
    for role in ROLES
]
CASE_IDS = [f"{m} {p} as {r}" for m, p, r, _ in CASES]


def _make_user(db, role, is_active=True):
    user = User(
        email=f"role_auth_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _call(method, path, user=None, token=None):
    if token is None and user is not None:
        token = create_access_token(user.id, user.role)
    headers = _bearer(token) if token else {}
    return client.request(method, path, json={}, headers=headers)


# SCRUM-241: every supported role against every role-gated endpoint

@pytest.mark.parametrize("method, path, role, allowed", CASES, ids=CASE_IDS)
def test_role_gate_allows_permitted_roles_and_blocks_the_rest(
    db, method, path, role, allowed
):
    user = _make_user(db, role)

    response = _call(method, path, user)

    if allowed:
        assert response.status_code not in (401, 403)
    else:
        assert response.status_code == 403


# SCRUM-241: unauthenticated and missing roles

@pytest.mark.parametrize(
    "method, path", [(m, p) for m, p, _ in ROLE_GATED]
)
def test_role_gated_endpoints_require_a_token(method, path):
    assert _call(method, path).status_code == 401


@pytest.mark.parametrize("role", [None, "", "guest"])
@pytest.mark.parametrize(
    "method, path", [(m, p) for m, p, _ in ROLE_GATED]
)
def test_user_without_a_valid_role_is_blocked(method, path, role):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=role, is_active=True
    )
    try:
        response = client.request(method, path, json={})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403


# SCRUM-241: the role comes from the database, not the token

@pytest.mark.parametrize(
    "method, path, allowed",
    [(m, p, a) for m, p, a in ROLE_GATED if "player" not in a],
)
def test_forged_role_claim_does_not_grant_access(db, method, path, allowed):
    player = _make_user(db, "player")
    forged = create_access_token(player.id, next(iter(allowed)))

    assert _call(method, path, token=forged).status_code == 403


@pytest.mark.parametrize(
    "method, path, allowed", ROLE_GATED
)
def test_inactive_user_is_blocked_even_with_the_right_role(
    db, method, path, allowed
):
    user = _make_user(db, next(iter(allowed)), is_active=False)

    assert _call(method, path, user).status_code == 401


# SCRUM-241: endpoints open to any signed-in role

@pytest.mark.parametrize("role", ROLES)
def test_any_authenticated_role_can_reach_open_endpoints(db, role):
    user = _make_user(db, role)

    response = _call("GET", f"/player-team/team/{MISSING}", user)

    assert response.status_code == 404


def test_open_endpoint_still_requires_a_token():
    assert _call("GET", f"/player-team/team/{MISSING}").status_code == 401