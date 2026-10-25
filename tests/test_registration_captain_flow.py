from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.user.models import User

client = TestClient(app)


def _make_user(db, role):
    user = User(
        email=f"captain_flow_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _bearer(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _create_tournament(organiser):
    start = datetime.now(timezone.utc) + timedelta(days=30)
    response = client.post(
        "/organiser/tournaments",
        json={
            "name": f"Captain Flow Cup {uuid4().hex[:8]}",
            "format": "knockout",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=5)).isoformat(),
        },
        headers=_bearer(organiser),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_team(organiser, captain):
    response = client.post(
        "/player-team/team",
        json={"name": f"Captain Flow Team {uuid4()}", "captain_id": captain.id},
        headers=_bearer(organiser),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _register(user, team, tournament):
    return client.post(
        "/registrations/",
        json={
            "tournament_id": tournament["id"],
            "team_id": team["id"],
            "registration_type": "team",
        },
        headers=_bearer(user),
    )


def test_real_player_role_captain_can_register_their_team(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    tournament = _create_tournament(organiser)
    team = _create_team(organiser, captain)

    response = _register(captain, team, tournament)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["team_id"] == team["id"]
    assert body["tournament_id"] == tournament["id"]
    assert body["status"] == "pending"


def test_player_who_is_not_the_captain_cannot_register_the_team(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    other_player = _make_user(db, "player")
    tournament = _create_tournament(organiser)
    team = _create_team(organiser, captain)

    response = _register(other_player, team, tournament)

    assert response.status_code == 403


def test_captain_sees_their_team_registration_in_my_registrations(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    tournament = _create_tournament(organiser)
    team = _create_team(organiser, captain)
    registration = _register(captain, team, tournament).json()

    response = client.get("/registrations/my", headers=_bearer(captain))

    assert response.status_code == 200
    assert registration["id"] in [r["id"] for r in response.json()]


def test_other_player_does_not_see_the_captains_team_registration(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    other_player = _make_user(db, "player")
    tournament = _create_tournament(organiser)
    team = _create_team(organiser, captain)
    registration = _register(captain, team, tournament).json()

    response = client.get("/registrations/my", headers=_bearer(other_player))

    assert response.status_code == 200
    assert registration["id"] not in [r["id"] for r in response.json()]