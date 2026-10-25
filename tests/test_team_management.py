from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.user.models import User

client = TestClient(app)

NON_ORGANISER_ROLES = ["player", "scorer", "spectator", "official", "captain"]
NON_CAPTAIN_ROLES = ["organiser", "player", "scorer", "spectator", "official"]

INVALID_FIELDS = [
    {"name": ""},
    {"name": "   "},
    {"name": "x" * 101},
    {"name": None},
    {"name": 123},
    {"captain_id": 0},
    {"captain_id": -1},
    {"captain_id": None},
    {"captain_id": "abc"},
    {"captain_id": 1.5},
]


def _make_user(db, role="player", is_active=True):
    user = User(
        email=f"team_mgmt_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _bearer(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _make_team(db, captain):
    team = Team(
        name=f"Team Management {uuid4()}",
        captain_id=captain.id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _payload(captain, **overrides):
    payload = {"name": f"Team Management {uuid4()}", "captain_id": captain.id}
    payload.update(overrides)
    return payload


def _post(user, payload):
    headers = _bearer(user) if user else {}
    return client.post("/player-team/team", json=payload, headers=headers)


def _team_count(db):
    return db.query(Team).count()


# SCRUM-243: creation stores the right values

def test_created_team_is_stored_with_the_right_values(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    before = _team_count(db)
    payload = _payload(captain)

    response = _post(organiser, payload)

    assert response.status_code == 201
    body = response.json()
    team = db.query(Team).filter(Team.id == body["id"]).one()
    assert team.name == payload["name"]
    assert team.captain_id == captain.id
    assert team.status == TeamStatus.ACTIVE
    assert team.created_at is not None
    assert _team_count(db) == before + 1


def test_team_name_is_trimmed_before_saving(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    name = f"Padded Team {uuid4()}"

    response = _post(organiser, _payload(captain, name=f"   {name}   "))

    assert response.status_code == 201
    assert response.json()["name"] == name
    assert db.query(Team).filter(Team.name == name).count() == 1


def test_team_name_of_exactly_100_characters_is_accepted(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    name = ("x" * 68) + uuid4().hex
    assert len(name) == 100

    response = _post(organiser, _payload(captain, name=name))

    assert response.status_code == 201
    assert response.json()["name"] == name


# SCRUM-243: invalid data is rejected and nothing is saved

@pytest.mark.parametrize("overrides", INVALID_FIELDS)
def test_invalid_team_fields_are_rejected_and_nothing_is_saved(db, overrides):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    before = _team_count(db)

    response = _post(organiser, _payload(captain, **overrides))

    assert response.status_code == 422
    assert _team_count(db) == before


@pytest.mark.parametrize("missing", ["name", "captain_id"])
def test_missing_required_team_field_is_rejected(db, missing):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    payload = _payload(captain)
    del payload[missing]
    before = _team_count(db)

    response = _post(organiser, payload)

    assert response.status_code == 422
    assert _team_count(db) == before


def test_empty_team_body_is_rejected(db):
    organiser = _make_user(db, "organiser")
    before = _team_count(db)

    response = _post(organiser, {})

    assert response.status_code == 422
    assert _team_count(db) == before


# SCRUM-243: duplicates

def test_duplicate_name_with_extra_spaces_does_not_create_a_second_team(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    name = f"Duplicate Team {uuid4()}"

    first = _post(organiser, _payload(captain, name=name))
    second = _post(organiser, _payload(captain, name=f"  {name}  "))

    assert first.status_code == 201
    assert second.status_code in (403, 409)
    assert db.query(Team).filter(Team.name == name).count() == 1


# SCRUM-243: authorization on creation

@pytest.mark.parametrize("role", NON_ORGANISER_ROLES)
def test_non_organiser_cannot_create_a_team_and_nothing_is_saved(db, role):
    user = _make_user(db, role)
    captain = _make_user(db, "player")
    before = _team_count(db)

    response = _post(user, _payload(captain))

    assert response.status_code == 403
    assert _team_count(db) == before


def test_creating_a_team_without_a_token_saves_nothing(db):
    captain = _make_user(db, "player")
    before = _team_count(db)

    response = _post(None, _payload(captain))

    assert response.status_code in (401, 403)
    assert _team_count(db) == before


def test_inactive_organiser_cannot_create_a_team(db):
    organiser = _make_user(db, "organiser", is_active=False)
    captain = _make_user(db, "player")
    before = _team_count(db)

    response = _post(organiser, _payload(captain))

    assert response.status_code == 401
    assert _team_count(db) == before


# SCRUM-243: retrieval

def test_created_team_can_be_retrieved_with_the_same_data(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "player")
    created = _post(organiser, _payload(captain)).json()

    response = client.get(
        f"/player-team/team/{created['id']}", headers=_bearer(organiser)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["name"] == created["name"]
    assert body["captain_id"] == captain.id
    assert body["status"] == "active"
    assert body["players"] == []


def test_non_numeric_team_id_is_rejected(db):
    user = _make_user(db, "organiser")

    response = client.get("/player-team/team/abc", headers=_bearer(user))

    assert response.status_code == 422


# SCRUM-243: ownership of status changes

@pytest.mark.parametrize("role", NON_CAPTAIN_ROLES)
def test_only_the_captain_can_change_team_status(db, role):
    captain = _make_user(db, "player")
    team = _make_team(db, captain)
    user = _make_user(db, role)

    response = client.patch(
        f"/player-team/team/{team.id}/status",
        json={"status": "inactive"},
        headers=_bearer(user),
    )

    assert response.status_code == 403
    db.refresh(team)
    assert team.status == TeamStatus.ACTIVE


def test_captain_of_another_team_cannot_change_this_teams_status(db):
    team = _make_team(db, _make_user(db, "player"))
    other_captain = _make_user(db, "player")
    _make_team(db, other_captain)

    response = client.patch(
        f"/player-team/team/{team.id}/status",
        json={"status": "suspended"},
        headers=_bearer(other_captain),
    )

    assert response.status_code == 403
    db.refresh(team)
    assert team.status == TeamStatus.ACTIVE