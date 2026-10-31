from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import BadRequestException
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.services.tournament_service import (
    can_transition_tournament_status,
    validate_tournament_status,
)
from app.modules.user.models import User

client = TestClient(app)

NON_ORGANISER_ROLES = ["player", "scorer", "spectator", "official", "captain"]


def _make_user(db, role="organiser"):
    user = User(
        email=f"tourn_mgmt_{uuid4()}@example.com",
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


def _payload(**overrides):
    start = datetime.now(timezone.utc) + timedelta(days=30)
    payload = {
        "name": f"Tournament Mgmt {uuid4().hex[:8]}",
        "format": "knockout",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=5)).isoformat(),
        "registration_open_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "registration_close_at": (start - timedelta(days=1)).isoformat(),
    }
    payload.update(overrides)
    return payload


def _count(db):
    return db.query(Tournament).count()


def _create(db, organiser=None, **overrides):
    organiser = organiser or _make_user(db)
    response = client.post(
        "/organiser/tournaments", json=_payload(**overrides), headers=_bearer(organiser)
    )
    assert response.status_code == 201, response.text
    return organiser, response.json()


# Second create endpoint: POST /tournaments/

def test_public_router_create_stores_owner_and_upcoming_status(db):
    organiser = _make_user(db)
    before = _count(db)

    response = client.post("/tournaments/", json=_payload(), headers=_bearer(organiser))

    assert response.status_code == 201
    body = response.json()
    assert body["organizer_id"] == organiser.id
    assert body["status"] == "upcoming"
    assert _count(db) == before + 1


@pytest.mark.parametrize("role", NON_ORGANISER_ROLES)
def test_public_router_create_rejects_non_organisers(db, role):
    user = _make_user(db, role)
    before = _count(db)

    response = client.post("/tournaments/", json=_payload(), headers=_bearer(user))

    assert response.status_code == 403
    assert _count(db) == before


def test_public_router_create_without_token_saves_nothing(db):
    before = _count(db)

    response = client.post("/tournaments/", json=_payload())

    assert response.status_code in (401, 403)
    assert _count(db) == before


def test_public_router_create_rejects_unsupported_format(db):
    organiser = _make_user(db)
    before = _count(db)

    response = client.post(
        "/tournaments/", json=_payload(format="bogus"), headers=_bearer(organiser)
    )

    assert response.status_code == 400
    assert _count(db) == before


# Schema validation: rejected with 422, nothing saved

INVALID_CREATE = [
    {"name": "ab"},
    {"name": "x" * 151},
    {"format": ""},
    {"format": "x" * 51},
    {"start_date": "not-a-date"},
    {"name": None},
]


@pytest.mark.parametrize("overrides", INVALID_CREATE)
def test_invalid_tournament_fields_are_rejected_and_nothing_is_saved(db, overrides):
    organiser = _make_user(db)
    before = _count(db)

    response = client.post(
        "/organiser/tournaments", json=_payload(**overrides), headers=_bearer(organiser)
    )

    assert response.status_code == 422
    assert _count(db) == before


def test_end_date_equal_to_start_date_is_rejected(db):
    organiser = _make_user(db)
    start = datetime.now(timezone.utc) + timedelta(days=30)
    before = _count(db)

    response = client.post(
        "/organiser/tournaments",
        json=_payload(start_date=start.isoformat(), end_date=start.isoformat()),
        headers=_bearer(organiser),
    )

    assert response.status_code == 422
    assert _count(db) == before


@pytest.mark.parametrize(
    "config",
    [
        {"number_of_teams": 1},
        {"number_of_teams": 8, "unknown_key": 1},
        {"number_of_teams": 8, "points_per_win": -1},
        {"number_of_teams": 8, "points_per_win": True},
        {"number_of_teams": 8, "tie_break_rules": "points"},
        {"number_of_teams": 8, "tie_break_rules": ["points", "points"]},
        {"number_of_teams": 8, "tie_break_rules": ["not_a_rule"]},
    ],
)
def test_invalid_format_config_is_rejected(db, config):
    organiser = _make_user(db)
    before = _count(db)

    response = client.post(
        "/organiser/tournaments",
        json=_payload(format="round_robin", format_config=config),
        headers=_bearer(organiser),
    )

    assert response.status_code == 422
    assert _count(db) == before


def test_valid_scoring_rules_are_stored(db):
    config = {
        "number_of_teams": 8,
        "points_per_win": 3,
        "points_per_draw": 1,
        "points_per_loss": 0,
        "tie_break_rules": ["points", "score_difference", "team_name"],
    }

    _, body = _create(db, format="round_robin", format_config=config)

    assert body["format_config"]["points_per_win"] == 3
    assert body["format_config"]["tie_break_rules"] == config["tie_break_rules"]


def test_format_config_on_a_knockout_tournament_is_rejected(db):
    organiser = _make_user(db)
    before = _count(db)

    response = client.post(
        "/organiser/tournaments",
        json=_payload(format="knockout", format_config={"number_of_teams": 8}),
        headers=_bearer(organiser),
    )

    assert response.status_code == 400
    assert _count(db) == before


@pytest.mark.parametrize("fmt", ["round_robin", "single_elimination", "double_elimination"])
def test_elimination_and_round_robin_formats_require_a_config(db, fmt):
    organiser = _make_user(db)
    before = _count(db)

    response = client.post(
        "/organiser/tournaments", json=_payload(format=fmt), headers=_bearer(organiser)
    )

    assert response.status_code == 400
    assert _count(db) == before


# Update rules

def test_update_cannot_change_status(db):
    organiser, created = _create(db)

    response = client.patch(
        f"/organiser/tournaments/{created['id']}",
        json={"status": "completed"},
        headers=_bearer(organiser),
    )

    assert response.status_code == 400
    tournament = db.query(Tournament).filter(Tournament.id == created["id"]).one()
    db.refresh(tournament)
    assert tournament.status == "upcoming"


def test_update_end_date_before_existing_start_date_is_rejected(db):
    organiser, created = _create(db)
    start = datetime.fromisoformat(created["start_date"])
    original_end = datetime.fromisoformat(created["end_date"])

    response = client.patch(
        f"/organiser/tournaments/{created['id']}",
        json={"end_date": (start - timedelta(days=1)).isoformat()},
        headers=_bearer(organiser),
    )

    assert response.status_code == 400
    tournament = db.query(Tournament).filter(Tournament.id == created["id"]).one()
    db.refresh(tournament)
    assert tournament.end_date.replace(tzinfo=None) == original_end.replace(tzinfo=None)


def test_partial_update_keeps_the_other_fields(db):
    organiser, created = _create(db)
    new_name = f"Renamed {uuid4().hex[:8]}"

    response = client.patch(
        f"/organiser/tournaments/{created['id']}",
        json={"name": new_name},
        headers=_bearer(organiser),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == new_name
    assert body["format"] == created["format"]
    assert body["organizer_id"] == created["organizer_id"]


def test_update_with_invalid_name_is_rejected(db):
    organiser, created = _create(db)

    response = client.patch(
        f"/organiser/tournaments/{created['id']}",
        json={"name": "ab"},
        headers=_bearer(organiser),
    )

    assert response.status_code == 422


# Public read routes

def test_public_list_filters_by_status(db):
    _, created = _create(db)

    upcoming = client.get("/tournaments/", params={"status": "upcoming"})
    archived = client.get("/tournaments/", params={"status": "archived"})

    assert upcoming.status_code == 200
    assert created["id"] in [t["id"] for t in upcoming.json()]
    assert created["id"] not in [t["id"] for t in archived.json()]


def test_public_get_unknown_tournament_returns_404(db):
    response = client.get("/tournaments/999999999")

    assert response.status_code == 404


@pytest.mark.parametrize("tournament_id", [0, -1])
def test_public_get_non_positive_id_is_rejected(db, tournament_id):
    response = client.get(f"/tournaments/{tournament_id}")

    assert response.status_code == 422


@pytest.mark.parametrize("suffix", ["standings", "leaderboard"])
def test_unpublished_tournament_standings_are_hidden(db, suffix):
    _, created = _create(db)

    response = client.get(f"/tournaments/{created['id']}/{suffix}")

    assert response.status_code == 404


@pytest.mark.parametrize("suffix", ["standings", "leaderboard"])
def test_unknown_tournament_standings_return_404(db, suffix):
    response = client.get(f"/tournaments/999999999/{suffix}")

    assert response.status_code == 404


# Status transition rules (pure logic)

@pytest.mark.parametrize(
    "current,new,allowed",
    [
        ("upcoming", "ongoing", True),
        ("ongoing", "completed", True),
        ("completed", "archived", True),
        ("upcoming", "completed", False),
        ("upcoming", "archived", False),
        ("ongoing", "upcoming", False),
        ("ongoing", "archived", False),
        ("completed", "ongoing", False),
        ("archived", "upcoming", False),
        ("archived", "completed", False),
        ("upcoming", "upcoming", False),
    ],
)
def test_status_transition_rules(current, new, allowed):
    assert can_transition_tournament_status(current, new) is allowed


def test_unknown_status_is_rejected():
    with pytest.raises(BadRequestException):
        validate_tournament_status("deleted")

    with pytest.raises(BadRequestException):
        can_transition_tournament_status("upcoming", "deleted")