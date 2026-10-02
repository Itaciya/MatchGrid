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
        email=f"player_profile_test_{uuid4()}@example.com",
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
        name=f"Player Profile Test Team {uuid4()}",
        captain_id=captain_id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _make_player(db):
    user = _make_user(db)
    team = _make_team(db, user.id)

    player = Player(
        user_id=user.id,
        team_id=team.id,
        first_name="John",
        last_name="Doe",
        is_active=True,
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    return player, user


def test_get_player_profile_returns_player(db):
    player, user = _make_player(db)

    response = client.get(
        f"/player-team/profile/{player.id}",
        headers=_auth_header(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == player.id
    assert data["user_id"] == player.user_id
    assert data["team_id"] == player.team_id
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["is_active"] is True


def test_get_player_profile_returns_404_for_nonexistent_player(db):
    user = _make_user(db)

    response = client.get(
        "/player-team/profile/999999",
        headers=_auth_header(user),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Player not found"


def test_get_player_profile_requires_authentication():
    response = client.get("/player-team/profile/1")

    assert response.status_code == 401

def test_organiser_can_update_player_status(db):
    player, player_user = _make_player(db)

    organiser = _make_user(
        db,
        email=f"organiser_status_test_{uuid4()}@example.com",
        role="organiser",
    )

    response = client.patch(
        f"/player-team/profile/{player.id}/status",
        json={"is_active": False},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == player.id
    assert data["is_active"] is False


def test_organiser_can_reactivate_player(db):
    player, player_user = _make_player(db)
    player.is_active = False
    db.commit()

    organiser = _make_user(
        db,
        email=f"organiser_reactivate_test_{uuid4()}@example.com",
        role="organiser",
    )

    response = client.patch(
        f"/player-team/profile/{player.id}/status",
        json={"is_active": True},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == player.id
    assert data["is_active"] is True


def test_player_cannot_update_player_status(db):
    player, player_user = _make_player(db)

    response = client.patch(
        f"/player-team/profile/{player.id}/status",
        json={"is_active": False},
        headers=_auth_header(player_user),
    )

    assert response.status_code == 403


def test_update_player_status_returns_404_for_nonexistent_player(db):
    organiser = _make_user(
        db,
        email=f"organiser_not_found_test_{uuid4()}@example.com",
        role="organiser",
    )

    response = client.patch(
        "/player-team/profile/999999/status",
        json={"is_active": False},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Player not found"

def test_create_player_rejects_duplicate_profile(db):
    user = _make_user(db)

    team = _make_team(db, user.id)

    player_data = {
        "team_id": team.id,
        "first_name": "John",
        "last_name": "Doe",
    }

    headers = _auth_header(user)

    response = client.post(
        "/player-team/profile",
        json=player_data,
        headers=headers,
    )

    assert response.status_code == 201

    duplicate_response = client.post(
        "/player-team/profile",
        json=player_data,
        headers=headers,
    )

    assert duplicate_response.status_code == 409
    assert (
        duplicate_response.json()["error"]["message"]
        == "Player profile already exists for this user"
    )

def test_player_can_update_own_profile(db):
    player, user = _make_player(db)

    response = client.patch(
        f"/player-team/profile/{player.id}",
        json={
            "first_name": "Updated",
            "last_name": "Player",
        },
        headers=_auth_header(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == player.id
    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Player"


def test_player_cannot_update_another_profile(db):
    player, player_user = _make_player(db)
    another_user = _make_user(
        db,
        email=f"another_player_{uuid4()}@example.com",
        role="player",
    )

    response = client.patch(
        f"/player-team/profile/{player.id}",
        json={
            "first_name": "Hacked",
        },
        headers=_auth_header(another_user),
    )

    assert response.status_code == 403
    assert (
        response.json()["error"]["message"]
        == "You can only update your own profile"
    )


def test_player_update_rejects_invalid_information(db):
    player, user = _make_player(db)

    response = client.patch(
        f"/player-team/profile/{player.id}",
        json={
            "first_name": "12345",
        },
        headers=_auth_header(user),
    )

    assert response.status_code == 422


def test_player_update_returns_404_for_nonexistent_player(db):
    user = _make_user(db)

    response = client.patch(
        "/player-team/profile/999999",
        json={
            "first_name": "Updated",
        },
        headers=_auth_header(user),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Player not found"