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
        email=f"remove_player_test_{uuid4()}@example.com",
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
        name=f"Remove Player Test Team {uuid4()}",
        captain_id=captain_id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def _make_player(
    db,
    user_id,
    team_id=None,
):
    player = Player(
        user_id=user_id,
        team_id=team_id,
        first_name="John",
        last_name="Doe",
        status="active",
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    return player


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_captain_can_remove_player_from_team(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    player_user = _make_user(
        db,
        email=f"team_player_{uuid4()}@example.com",
    )
    player = _make_player(
        db,
        player_user.id,
        team_id=team.id,
    )

    response = client.delete(
        f"/player-team/team/{team.id}/players/{player.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == player.id
    assert data["team_id"] is None


def test_player_is_removed_from_team_roster(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    player_user = _make_user(
        db,
        email=f"roster_player_{uuid4()}@example.com",
    )
    player = _make_player(
        db,
        player_user.id,
        team_id=team.id,
    )

    response = client.delete(
        f"/player-team/team/{team.id}/players/{player.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 200

    db.refresh(player)

    assert player.team_id is None


def test_non_captain_cannot_remove_player_from_team(db):
    captain = _make_user(db)
    other_user = _make_user(
        db,
        email=f"other_user_{uuid4()}@example.com",
    )
    team = _make_team(db, captain.id)

    player_user = _make_user(
        db,
        email=f"team_player_{uuid4()}@example.com",
    )
    player = _make_player(
        db,
        player_user.id,
        team_id=team.id,
    )

    response = client.delete(
        f"/player-team/team/{team.id}/players/{player.id}",
        headers=_auth_header(other_user),
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == (
        "Only the team captain can remove players"
    )


def test_player_not_in_team_cannot_be_removed(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    player_user = _make_user(
        db,
        email=f"other_player_{uuid4()}@example.com",
    )
    player = _make_player(
        db,
        player_user.id,
        team_id=None,
    )

    response = client.delete(
        f"/player-team/team/{team.id}/players/{player.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "Player does not belong to this team"
    )


def test_remove_player_returns_404_for_nonexistent_player(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    response = client.delete(
        f"/player-team/team/{team.id}/players/999999",
        headers=_auth_header(captain),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Player not found"


def test_remove_player_returns_404_for_nonexistent_team(db):
    captain = _make_user(db)

    player_user = _make_user(
        db,
        email=f"team_player_{uuid4()}@example.com",
    )
    player = _make_player(
        db,
        player_user.id,
        team_id=None,
    )

    response = client.delete(
        f"/player-team/team/999999/players/{player.id}",
        headers=_auth_header(captain),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Team not found"


def test_remove_player_requires_authentication(db):
    captain = _make_user(db)
    team = _make_team(db, captain.id)

    player_user = _make_user(
        db,
        email=f"team_player_{uuid4()}@example.com",
    )
    player = _make_player(
        db,
        player_user.id,
        team_id=team.id,
    )

    response = client.delete(
        f"/player-team/team/{team.id}/players/{player.id}",
    )

    assert response.status_code == 401