import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import OfficialAssignment
from app.modules.score.models.score import Score
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


def _make_match(db, status="live"):
    organiser = _make_user(db, "organiser")

    tournament = Tournament(
        name=f"Score Test Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    match = Match(
        tournament_id=tournament.id,
        match_number=1,
        scheduled_at=datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        status=status,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def _assign(db, match, user, assignment_type="referee", status="active"):
    assignment = OfficialAssignment(
        match_id=match.id,
        official_id=user.id,
        assignment_type=assignment_type,
        status=status,
    )
    db.add(assignment)
    db.commit()
    return assignment


def _assigned_official(db, match, role="scorer"):
    user = _make_user(db, role)
    _assign(db, match, user)
    return user


def _make_score(db, match, **overrides):
    defaults = dict(match_id=match.id, team_a_score=1, team_b_score=0)
    defaults.update(overrides)
    score = Score(**defaults)
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


def _payload(match, team_a=2, team_b=1):
    return {"match_id": match.id, "team_a_score": team_a, "team_b_score": team_b}


def _score_count(db, match):
    return db.query(Score).filter(Score.match_id == match.id).count()


# --- Submission: who may submit ---

@pytest.mark.parametrize("role", ["scorer", "official"])
def test_assigned_official_can_submit_a_score(db, role):
    match = _make_match(db)
    user = _assigned_official(db, match, role)

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(match),
        headers=_auth_header(user),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["match_id"] == match.id
    assert data["team_a_score"] == 2
    assert data["team_b_score"] == 1
    assert data["is_verified"] is False
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_submitted_score_is_persisted(db):
    match = _make_match(db)
    user = _assigned_official(db, match)

    client.post(
        f"/matches/{match.id}/score",
        json=_payload(match, 3, 0),
        headers=_auth_header(user),
    )

    score = db.query(Score).filter(Score.match_id == match.id).first()
    assert score is not None
    assert (score.team_a_score, score.team_b_score) == (3, 0)
    assert score.is_verified is False


def test_unassigned_official_cannot_submit_a_score(db):
    match = _make_match(db)
    user = _make_user(db, "scorer")

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(match),
        headers=_auth_header(user),
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "You are not assigned to this match"
    assert _score_count(db, match) == 0


def test_assignment_to_another_match_does_not_authorise_submission(db):
    other_match = _make_match(db)
    target_match = _make_match(db)
    user = _assigned_official(db, other_match)

    response = client.post(
        f"/matches/{target_match.id}/score",
        json=_payload(target_match),
        headers=_auth_header(user),
    )

    assert response.status_code == 403
    assert _score_count(db, target_match) == 0


def test_inactive_assignment_does_not_authorise_submission(db):
    match = _make_match(db)
    user = _make_user(db, "scorer")
    _assign(db, match, user, status="cancelled")

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(match),
        headers=_auth_header(user),
    )

    assert response.status_code == 403
    assert _score_count(db, match) == 0


@pytest.mark.parametrize("role", ["player", "spectator", "organiser"])
def test_other_roles_cannot_submit_even_if_assigned(db, role):
    match = _make_match(db)
    user = _make_user(db, role)
    _assign(db, match, user)

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(match),
        headers=_auth_header(user),
    )

    assert response.status_code == 403
    assert _score_count(db, match) == 0


def test_submission_without_a_token_is_rejected(db):
    match = _make_match(db)

    response = client.post(f"/matches/{match.id}/score", json=_payload(match))

    assert response.status_code == 401
    assert _score_count(db, match) == 0


def test_submission_for_unknown_match_returns_404(db):
    user = _make_user(db, "scorer")

    response = client.post(
        "/matches/999999/score",
        json={"match_id": 999999, "team_a_score": 1, "team_b_score": 0},
        headers=_auth_header(user),
    )

    assert response.status_code == 404


# --- Submission: validation and rules ---

def test_body_match_id_must_match_the_path(db):
    match = _make_match(db)
    other_match = _make_match(db)
    user = _assigned_official(db, match)

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(other_match),
        headers=_auth_header(user),
    )

    assert response.status_code == 400
    assert _score_count(db, match) == 0
    assert _score_count(db, other_match) == 0


def test_invalid_score_data_is_rejected(db):
    match = _make_match(db)
    user = _assigned_official(db, match)

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(match, -1, 0),
        headers=_auth_header(user),
    )

    assert response.status_code == 422
    assert _score_count(db, match) == 0


@pytest.mark.parametrize("extra", ["is_verified", "created_at", "updated_at"])
def test_client_cannot_supply_server_controlled_fields(db, extra):
    match = _make_match(db)
    user = _assigned_official(db, match)
    payload = _payload(match)
    payload[extra] = True if extra == "is_verified" else "2000-01-01T00:00:00Z"

    response = client.post(
        f"/matches/{match.id}/score",
        json=payload,
        headers=_auth_header(user),
    )

    assert response.status_code == 422
    assert _score_count(db, match) == 0


@pytest.mark.parametrize("status", ["scheduled", "cancelled"])
def test_score_cannot_be_submitted_unless_match_is_live(db, status):
    match = _make_match(db, status=status)
    user = _assigned_official(db, match)

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(match),
        headers=_auth_header(user),
    )

    assert response.status_code == 409
    assert "live" in response.json()["error"]["message"]
    assert _score_count(db, match) == 0


def test_duplicate_submission_is_rejected_and_keeps_original(db):
    match = _make_match(db)
    user = _assigned_official(db, match)
    score = _make_score(db, match, team_a_score=4, team_b_score=4)

    response = client.post(
        f"/matches/{match.id}/score",
        json=_payload(match, 0, 0),
        headers=_auth_header(user),
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["error"]["message"]
    db.refresh(score)
    assert (score.team_a_score, score.team_b_score) == (4, 4)


# --- Update: who may update ---

def test_assigned_official_can_update_a_score(db):
    match = _make_match(db)
    user = _assigned_official(db, match)
    score = _make_score(db, match)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 5, "team_b_score": 3},
        headers=_auth_header(user),
    )

    assert response.status_code == 200
    db.refresh(score)
    assert (score.team_a_score, score.team_b_score) == (5, 3)


def test_partial_update_changes_only_the_given_score(db):
    match = _make_match(db)
    user = _assigned_official(db, match)
    score = _make_score(db, match, team_a_score=2, team_b_score=2)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_b_score": 3},
        headers=_auth_header(user),
    )

    assert response.status_code == 200
    db.refresh(score)
    assert (score.team_a_score, score.team_b_score) == (2, 3)


def test_unassigned_official_cannot_update_a_score(db):
    match = _make_match(db)
    user = _make_user(db, "scorer")
    score = _make_score(db, match, team_a_score=1, team_b_score=0)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 9},
        headers=_auth_header(user),
    )

    assert response.status_code == 403
    db.refresh(score)
    assert score.team_a_score == 1


@pytest.mark.parametrize("role", ["player", "spectator", "organiser"])
def test_other_roles_cannot_update_even_if_assigned(db, role):
    match = _make_match(db)
    user = _make_user(db, role)
    _assign(db, match, user)
    score = _make_score(db, match, team_a_score=1, team_b_score=0)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 9},
        headers=_auth_header(user),
    )

    assert response.status_code == 403
    db.refresh(score)
    assert score.team_a_score == 1


def test_update_without_a_token_is_rejected(db):
    match = _make_match(db)
    _make_score(db, match)

    response = client.patch(
        f"/matches/{match.id}/score", json={"team_a_score": 9}
    )

    assert response.status_code == 401


# --- Update: rules and finalized protection ---

def test_update_with_no_score_submitted_returns_404(db):
    match = _make_match(db)
    user = _assigned_official(db, match)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 1},
        headers=_auth_header(user),
    )

    assert response.status_code == 404


def test_empty_update_is_rejected(db):
    match = _make_match(db)
    user = _assigned_official(db, match)
    _make_score(db, match)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={},
        headers=_auth_header(user),
    )

    assert response.status_code == 422


def test_verified_score_cannot_be_modified(db):
    match = _make_match(db)
    user = _assigned_official(db, match)
    score = _make_score(db, match, team_a_score=1, team_b_score=0, is_verified=True,
        verification_status="verified")

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 9},
        headers=_auth_header(user),
    )

    assert response.status_code == 409
    assert "Finalized" in response.json()["error"]["message"]
    db.refresh(score)
    assert score.team_a_score == 1


def test_score_of_a_completed_match_cannot_be_modified(db):
    match = _make_match(db, status="completed")
    user = _assigned_official(db, match)
    score = _make_score(db, match, team_a_score=1, team_b_score=0)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 9},
        headers=_auth_header(user),
    )

    assert response.status_code == 409
    assert "Finalized" in response.json()["error"]["message"]
    db.refresh(score)
    assert score.team_a_score == 1


def test_score_cannot_be_updated_unless_match_is_live(db):
    match = _make_match(db, status="scheduled")
    user = _assigned_official(db, match)
    score = _make_score(db, match, team_a_score=1, team_b_score=0)

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 9},
        headers=_auth_header(user),
    )

    assert response.status_code == 409
    assert "live" in response.json()["error"]["message"]
    db.refresh(score)
    assert score.team_a_score == 1


def test_update_refreshes_the_server_side_timestamp(db):
    match = _make_match(db)
    user = _assigned_official(db, match)
    score = _make_score(db, match)
    original_updated_at = score.updated_at

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 7},
        headers=_auth_header(user),
    )

    assert response.status_code == 200
    db.refresh(score)
    assert score.updated_at > original_updated_at
