import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

client = TestClient(app)


def _make_user(db, role):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _make_team(db, captain_id):
    team = Team(
        name=f"Start Test Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _make_match(db, status="scheduled", with_teams=True, started_at=None):
    organiser = _make_user(db, "organiser")

    tournament = Tournament(
        name=f"Start Test Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    team_a_id = team_b_id = None
    if with_teams:
        team_a_id = _make_team(db, organiser.id).id
        team_b_id = _make_team(db, organiser.id).id

    match = Match(
        tournament_id=tournament.id,
        match_number=1,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        scheduled_at=datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        status=status,
        started_at=started_at,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@pytest.mark.parametrize("role", ["scorer", "official"])
def test_authorised_roles_can_start_a_scheduled_match(db, role):
    user = _make_user(db, role)
    match = _make_match(db)

    response = client.post(
        f"/matches/{match.id}/start", headers=_auth_header(user)
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == match.id
    assert data["status"] == "live"
    assert data["started_at"] is not None


def test_start_is_persisted_to_the_database(db):
    user = _make_user(db, "scorer")
    match = _make_match(db)

    client.post(f"/matches/{match.id}/start", headers=_auth_header(user))

    db.refresh(match)
    assert match.status == "live"
    assert match.started_at is not None


def test_start_time_comes_from_the_server_not_the_client(db):
    user = _make_user(db, "scorer")
    match = _make_match(db)

    before = datetime.now(timezone.utc)
    response = client.post(
        f"/matches/{match.id}/start",
        json={"started_at": "2000-01-01T00:00:00Z"},
        headers=_auth_header(user),
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 200
    started_at = datetime.fromisoformat(response.json()["started_at"])
    assert before <= started_at <= after


@pytest.mark.parametrize("status", ["live", "completed", "cancelled"])
def test_invalid_status_transition_is_rejected(db, status):
    user = _make_user(db, "scorer")
    match = _make_match(db, status=status)

    response = client.post(
        f"/matches/{match.id}/start", headers=_auth_header(user)
    )

    assert response.status_code == 409
    assert f"'{status}'" in response.json()["error"]["message"]


def test_rejected_start_does_not_modify_the_match(db):
    user = _make_user(db, "scorer")
    original_start = datetime(2099, 1, 2, 10, 5, tzinfo=timezone.utc)
    match = _make_match(db, status="live", started_at=original_start)

    client.post(f"/matches/{match.id}/start", headers=_auth_header(user))

    db.refresh(match)
    assert match.status == "live"
    assert match.started_at == original_start


def test_match_without_both_teams_cannot_start(db):
    user = _make_user(db, "scorer")
    match = _make_match(db, with_teams=False)

    response = client.post(
        f"/matches/{match.id}/start", headers=_auth_header(user)
    )

    assert response.status_code == 400
    db.refresh(match)
    assert match.status == "scheduled"
    assert match.started_at is None


def test_starting_a_nonexistent_match_returns_404(db):
    user = _make_user(db, "scorer")

    response = client.post("/matches/999999/start", headers=_auth_header(user))

    assert response.status_code == 404


@pytest.mark.parametrize("role", ["player", "spectator", "organiser"])
def test_other_roles_cannot_start_a_match(db, role):
    user = _make_user(db, role)
    match = _make_match(db)

    response = client.post(
        f"/matches/{match.id}/start", headers=_auth_header(user)
    )

    assert response.status_code == 403
    db.refresh(match)
    assert match.status == "scheduled"


def test_start_without_a_token_is_rejected(db):
    match = _make_match(db)

    response = client.post(f"/matches/{match.id}/start")

    assert response.status_code == 401
