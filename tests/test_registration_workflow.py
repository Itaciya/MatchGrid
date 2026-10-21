from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.player_team.models.team import Team
from app.modules.registration.models.registration import Registration
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

client = TestClient(app)

MISSING = 999999999
STATUSES = ["pending", "approved", "rejected", "cancelled"]
FINAL_STATUSES = ["approved", "rejected", "cancelled"]
# Only pending can move, and only to approved, rejected or cancelled.
INVALID_TRANSITIONS = [(a, b) for a in FINAL_STATUSES for b in STATUSES] + [
    ("pending", "pending")
]


def _make_user(db, role):
    user = User(
        email=f"reg_workflow_{uuid4()}@example.com",
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


def _make_tournament(db, organizer, **overrides):
    defaults = dict(
        name=f"Registration Workflow {uuid4()}",
        description="Test",
        format="knockout",
        start_date=datetime(2099, 6, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 6, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer.id,
    )
    defaults.update(overrides)
    tournament = Tournament(**defaults)
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def _make_team(db, captain):
    team = Team(
        name=f"Registration Workflow Team {uuid4()}",
        captain_id=captain.id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _make_registration(db, team, tournament, status="pending", note=None):
    registration = Registration(
        tournament_id=tournament.id,
        team_id=team.id,
        player_id=None,
        registration_type="team",
        status=status,
        note=note,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return registration


def _setup(db):
    organiser = _make_user(db, "organiser")
    captain = _make_user(db, "captain")
    team = _make_team(db, captain)
    tournament = _make_tournament(db, organiser)
    return organiser, captain, team, tournament


def _payload(team, tournament, **overrides):
    payload = {
        "tournament_id": tournament.id,
        "team_id": team.id,
        "registration_type": "team",
    }
    payload.update(overrides)
    return payload


def _count(db, tournament, team):
    return (
        db.query(Registration)
        .filter(
            Registration.tournament_id == tournament.id,
            Registration.team_id == team.id,
        )
        .count()
    )


def _set_status(registration_id, new_status, user):
    return client.patch(
        f"/registrations/{registration_id}/status",
        params={"new_status": new_status},
        headers=_bearer(user),
    )


# SCRUM-244: registration creation

def test_captain_can_register_team_and_it_starts_pending(db):
    _, captain, team, tournament = _setup(db)

    response = client.post(
        "/registrations/",
        json=_payload(team, tournament, note="See you there"),
        headers=_bearer(captain),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["registration_type"] == "team"
    assert body["team_id"] == team.id
    assert body["player_id"] is None
    assert body["tournament_id"] == tournament.id
    assert body["reviewed_at"] is None
    assert body["note"] == "See you there"
    assert _count(db, tournament, team) == 1


def test_duplicate_team_registration_is_rejected(db):
    _, captain, team, tournament = _setup(db)
    first = client.post(
        "/registrations/", json=_payload(team, tournament), headers=_bearer(captain)
    )

    second = client.post(
        "/registrations/", json=_payload(team, tournament), headers=_bearer(captain)
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert _count(db, tournament, team) == 1


def test_same_team_can_register_for_different_tournaments(db):
    organiser, captain, team, tournament = _setup(db)
    other_tournament = _make_tournament(db, organiser)

    first = client.post(
        "/registrations/", json=_payload(team, tournament), headers=_bearer(captain)
    )
    second = client.post(
        "/registrations/",
        json=_payload(team, other_tournament),
        headers=_bearer(captain),
    )

    assert first.status_code == 201
    assert second.status_code == 201


def test_only_the_teams_own_captain_can_register_it(db):
    _, _, team, tournament = _setup(db)
    other_captain = _make_user(db, "captain")

    response = client.post(
        "/registrations/",
        json=_payload(team, tournament),
        headers=_bearer(other_captain),
    )

    assert response.status_code == 403
    assert _count(db, tournament, team) == 0


def test_registering_a_nonexistent_team_returns_404(db):
    _, captain, team, tournament = _setup(db)

    response = client.post(
        "/registrations/",
        json=_payload(team, tournament, team_id=MISSING),
        headers=_bearer(captain),
    )

    assert response.status_code == 404


def test_registering_for_a_nonexistent_tournament_returns_404(db):
    _, captain, team, tournament = _setup(db)

    response = client.post(
        "/registrations/",
        json=_payload(team, tournament, tournament_id=MISSING),
        headers=_bearer(captain),
    )

    assert response.status_code == 404


def test_registration_is_closed_once_the_tournament_has_started(db):
    organiser, captain, team, _ = _setup(db)
    started = _make_tournament(
        db, organiser, start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )

    response = client.post(
        "/registrations/", json=_payload(team, started), headers=_bearer(captain)
    )

    assert response.status_code == 400
    assert _count(db, started, team) == 0


def test_registration_is_closed_for_tournaments_that_are_not_upcoming(db):
    organiser, captain, team, _ = _setup(db)
    finished = _make_tournament(db, organiser, status="completed")

    response = client.post(
        "/registrations/", json=_payload(team, finished), headers=_bearer(captain)
    )

    assert response.status_code == 400
    assert _count(db, finished, team) == 0


def test_player_type_registration_is_rejected_on_the_team_endpoint(db):
    _, captain, team, tournament = _setup(db)

    response = client.post(
        "/registrations/",
        json={
            "tournament_id": tournament.id,
            "player_id": 1,
            "registration_type": "player",
        },
        headers=_bearer(captain),
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "overrides",
    [
        {"team_id": None},
        {"player_id": 1},
        {"tournament_id": 0},
        {"team_id": 0},
        {"registration_type": "league"},
        {"registration_type": None},
    ],
)
def test_invalid_registration_bodies_are_rejected(db, overrides):
    _, captain, team, tournament = _setup(db)

    response = client.post(
        "/registrations/",
        json=_payload(team, tournament, **overrides),
        headers=_bearer(captain),
    )

    assert response.status_code == 422
    assert _count(db, tournament, team) == 0


# SCRUM-244: approval, rejection and cancellation

def test_organiser_approves_a_pending_registration(db):
    organiser, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament)

    response = client.patch(
        f"/registrations/{registration.id}/approve", headers=_bearer(organiser)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    db.refresh(registration)
    assert registration.status == "approved"
    assert registration.reviewed_at is not None


def test_organiser_rejects_a_pending_registration(db):
    organiser, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament)

    response = client.patch(
        f"/registrations/{registration.id}/reject", headers=_bearer(organiser)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    db.refresh(registration)
    assert registration.status == "rejected"
    assert registration.reviewed_at is not None


@pytest.mark.parametrize("new_status", FINAL_STATUSES)
def test_status_endpoint_moves_pending_to_each_final_status(db, new_status):
    organiser, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament)

    response = _set_status(registration.id, new_status, organiser)

    assert response.status_code == 200
    assert response.json()["status"] == new_status
    db.refresh(registration)
    assert registration.status == new_status
    assert registration.reviewed_at is not None


@pytest.mark.parametrize("current, target", INVALID_TRANSITIONS)
def test_invalid_status_transitions_are_rejected_and_change_nothing(
    db, current, target
):
    organiser, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament, status=current)

    response = _set_status(registration.id, target, organiser)

    assert response.status_code == 400
    db.refresh(registration)
    assert registration.status == current


@pytest.mark.parametrize("current", FINAL_STATUSES)
@pytest.mark.parametrize("action", ["approve", "reject"])
def test_only_pending_registrations_can_be_approved_or_rejected(
    db, current, action
):
    organiser, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament, status=current)

    response = client.patch(
        f"/registrations/{registration.id}/{action}", headers=_bearer(organiser)
    )

    assert response.status_code == 400
    db.refresh(registration)
    assert registration.status == current


@pytest.mark.parametrize("path", ["approve", "reject", "status"])
def test_workflow_on_a_nonexistent_registration_returns_404(db, path):
    organiser, _, _, _ = _setup(db)

    response = client.patch(
        f"/registrations/{MISSING}/{path}",
        params={"new_status": "approved"},
        headers=_bearer(organiser),
    )

    assert response.status_code == 404


def test_status_endpoint_rejects_an_unknown_status_value(db):
    organiser, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament)

    response = _set_status(registration.id, "confirmed", organiser)

    assert response.status_code == 422
    db.refresh(registration)
    assert registration.status == "pending"


# SCRUM-244: unauthorized approval is blocked

@pytest.mark.parametrize("role", ["captain", "player", "spectator", "scorer", "official"])
@pytest.mark.parametrize("path", ["approve", "reject", "status"])
def test_non_organisers_cannot_change_registration_status(db, role, path):
    _, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament)
    user = _make_user(db, role)

    response = client.patch(
        f"/registrations/{registration.id}/{path}",
        params={"new_status": "approved"},
        headers=_bearer(user),
    )

    assert response.status_code == 403
    db.refresh(registration)
    assert registration.status == "pending"
    assert registration.reviewed_at is None


@pytest.mark.parametrize("path", ["approve", "reject", "status"])
def test_status_changes_require_authentication(db, path):
    _, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament)

    response = client.patch(
        f"/registrations/{registration.id}/{path}",
        params={"new_status": "approved"},
    )

    assert response.status_code in (401, 403)
    db.refresh(registration)
    assert registration.status == "pending"


# SCRUM-244: editing a registration

def test_captain_can_update_the_note_on_a_pending_registration(db):
    _, captain, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament, note="old")

    response = client.patch(
        f"/registrations/{registration.id}",
        json={"note": "new"},
        headers=_bearer(captain),
    )

    assert response.status_code == 200
    db.refresh(registration)
    assert registration.note == "new"


def test_update_without_a_note_keeps_the_existing_note(db):
    _, captain, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament, note="keep me")

    response = client.patch(
        f"/registrations/{registration.id}", json={}, headers=_bearer(captain)
    )

    assert response.status_code == 200
    db.refresh(registration)
    assert registration.note == "keep me"


def test_another_captain_cannot_update_the_registration(db):
    _, _, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament, note="old")
    other_captain = _make_user(db, "captain")

    response = client.patch(
        f"/registrations/{registration.id}",
        json={"note": "hijacked"},
        headers=_bearer(other_captain),
    )

    assert response.status_code == 403
    db.refresh(registration)
    assert registration.note == "old"


@pytest.mark.parametrize("current", FINAL_STATUSES)
def test_only_pending_registrations_can_be_updated(db, current):
    _, captain, team, tournament = _setup(db)
    registration = _make_registration(db, team, tournament, status=current, note="old")

    response = client.patch(
        f"/registrations/{registration.id}",
        json={"note": "new"},
        headers=_bearer(captain),
    )

    assert response.status_code == 400
    db.refresh(registration)
    assert registration.note == "old"


def test_updating_a_nonexistent_registration_returns_404(db):
    _, captain, _, _ = _setup(db)

    response = client.patch(
        f"/registrations/{MISSING}", json={"note": "x"}, headers=_bearer(captain)
    )

    assert response.status_code == 404


# SCRUM-244: listing

def test_pending_list_contains_only_pending_registrations_of_that_tournament(db):
    organiser, captain, team, tournament = _setup(db)
    other_tournament = _make_tournament(db, organiser)
    pending = _make_registration(db, team, tournament)
    for status in ("approved", "rejected", "cancelled"):
        _make_registration(db, _make_team(db, captain), tournament, status=status)
    _make_registration(db, _make_team(db, captain), other_tournament)

    response = client.get(
        f"/registrations/pending/{tournament.id}", headers=_bearer(organiser)
    )

    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [pending.id]


def test_pending_list_for_a_nonexistent_tournament_returns_404(db):
    organiser, _, _, _ = _setup(db)

    response = client.get(
        f"/registrations/pending/{MISSING}", headers=_bearer(organiser)
    )

    assert response.status_code == 404


def test_captain_sees_only_their_own_registrations(db):
    organiser, captain, team, tournament = _setup(db)
    mine = _make_registration(db, team, tournament)
    other_captain = _make_user(db, "captain")
    _make_registration(db, _make_team(db, other_captain), tournament)

    response = client.get("/registrations/my", headers=_bearer(captain))

    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [mine.id]


def test_player_without_a_profile_has_no_registrations(db):
    player = _make_user(db, "player")

    response = client.get("/registrations/my", headers=_bearer(player))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("role", ["organiser", "spectator", "scorer", "official"])
def test_other_roles_cannot_view_my_registrations(db, role):
    user = _make_user(db, role)

    response = client.get("/registrations/my", headers=_bearer(user))

    assert response.status_code == 403