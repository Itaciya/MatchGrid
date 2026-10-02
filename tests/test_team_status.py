from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.player_team.models.team import Team
from app.modules.user.models import User


client = TestClient(app)


def _make_user(db, **overrides):
    defaults = dict(
        email=f"team_status_test_{uuid4()}@example.com",
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


def _make_team(db, captain_id, status="active"):
    team = Team(
        name=f"Team Status Test {uuid4()}",
        captain_id=captain_id,
        status=status,
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_captain_can_update_team_status(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.patch(
        f"/player-team/team/{team.id}/status",
        json={"status": "inactive"},
        headers=_auth_header(captain),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == team.id
    assert data["status"] == "inactive"


def test_team_status_is_stored_correctly(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.patch(
        f"/player-team/team/{team.id}/status",
        json={"status": "suspended"},
        headers=_auth_header(captain),
    )

    assert response.status_code == 200

    db.refresh(team)

    assert team.status == "suspended"


def test_non_captain_cannot_update_team_status(db):
    captain = _make_user(db)
    other_user = _make_user(
        db,
        email=f"other_user_{uuid4()}@example.com",
    )
    team = _make_team(db, captain.id)

    response = client.patch(
        f"/player-team/team/{team.id}/status",
        json={"status": "inactive"},
        headers=_auth_header(other_user),
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == (
        "Only the team captain can update team status"
    )


def test_invalid_team_status_is_rejected(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.patch(
        f"/player-team/team/{team.id}/status",
        json={"status": "invalid_status"},
        headers=_auth_header(captain),
    )

    assert response.status_code == 422


def test_update_team_status_returns_404_for_nonexistent_team(db):
    captain = _make_user(db)

    response = client.patch(
        "/player-team/team/999999/status",
        json={"status": "inactive"},
        headers=_auth_header(captain),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Team not found"


def test_update_team_status_requires_authentication(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.patch(
        f"/player-team/team/{team.id}/status",
        json={"status": "inactive"},
    )

    assert response.status_code == 401


def test_captain_can_set_each_valid_team_status(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    for status in ["active", "inactive", "suspended"]:
        response = client.patch(
            f"/player-team/team/{team.id}/status",
            json={"status": status},
            headers=_auth_header(captain),
        )

        assert response.status_code == 200
        assert response.json()["status"] == status
