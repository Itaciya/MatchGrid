from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.user.models import User


client = TestClient(app)


def _make_user(db, **overrides):
    defaults = dict(
        email=f"team_retrieval_test_{uuid4()}@example.com",
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


def _make_team(db, captain_id):
    team = Team(
        name=f"Team Retrieval Test {uuid4()}",
        captain_id=captain_id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def _make_player(db, team_id, user_id, first_name, last_name):
    player = Player(
        user_id=user_id,
        team_id=team_id,
        first_name=first_name,
        last_name=last_name,
        status="active",
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    return player


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_get_team_returns_team_information(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.get(
        f"/player-team/team/{team.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == team.id
    assert data["name"] == team.name
    assert data["captain_id"] == captain.id
    assert data["status"] == "active"
    assert "created_at" in data
    assert "updated_at" in data


def test_get_team_returns_roster(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    player_user = _make_user(
        db,
        email=f"roster_player_{uuid4()}@example.com",
    )

    player = _make_player(
        db,
        team.id,
        player_user.id,
        "John",
        "Doe",
    )

    response = client.get(
        f"/player-team/team/{team.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["players"]) == 1

    roster_player = data["players"][0]

    assert roster_player["id"] == player.id
    assert roster_player["user_id"] == player.user_id
    assert roster_player["team_id"] == team.id
    assert roster_player["first_name"] == "John"
    assert roster_player["last_name"] == "Doe"


def test_get_team_returns_empty_roster_when_team_has_no_players(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.get(
        f"/player-team/team/{team.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 200
    assert response.json()["players"] == []


def test_get_team_returns_404_for_nonexistent_team(db):
    user = _make_user(db)

    response = client.get(
        "/player-team/team/999999",
        headers=_auth_header(user),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Team not found"


def test_get_team_requires_authentication(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.get(
        f"/player-team/team/{team.id}",
    )

    assert response.status_code == 401


def test_get_team_does_not_expose_restricted_information(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.get(
        f"/player-team/team/{team.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 200

    data = response.json()

    assert "password_hash" not in data
    assert "password" not in data