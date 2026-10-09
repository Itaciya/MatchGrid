import uuid
from datetime import datetime, timezone
from app.modules.dispute.models.dispute import Dispute
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictException
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import OfficialAssignment
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.score.models.score import Score
from app.modules.score.services.score_verification_service import (
    ALLOWED_TRANSITIONS,
    ensure_transition_allowed,
)
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
        name=f"Review Test Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _make_match(db, status="live", with_teams=True):
    """Returns (match, organiser). The organiser owns the match's tournament."""
    organiser = _make_user(db, "organiser")

    tournament = Tournament(
        name=f"Review Test Tournament {uuid.uuid4()}",
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
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match, organiser


def _make_score(db, match, verification_status="pending", **overrides):
    defaults = dict(
        match_id=match.id,
        team_a_score=2,
        team_b_score=1,
        verification_status=verification_status,
        is_verified=(verification_status == "verified"),
    )
    defaults.update(overrides)
    score = Score(**defaults)
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


def _assign(db, match, user):
    db.add(
        OfficialAssignment(
            match_id=match.id,
            official_id=user.id,
            assignment_type="referee",
            status="active",
        )
    )
    db.commit()


def _review(match, user, status):
    return client.patch(
        f"/matches/{match.id}/score/verification",
        json={"status": status},
        headers=_auth_header(user),
    )


# --- Reviewing: the happy paths ---

def test_owner_can_verify_a_pending_score(db):
    match, organiser = _make_match(db)
    score = _make_score(db, match)

    before = datetime.now(timezone.utc)
    response = _review(match, organiser, "verified")
    after = datetime.now(timezone.utc)

    assert response.status_code == 200
    data = response.json()
    assert data["verification_status"] == "verified"
    assert data["is_verified"] is True
    assert data["reviewed_by_id"] == organiser.id
    assert before <= datetime.fromisoformat(data["reviewed_at"]) <= after

    db.refresh(score)
    assert score.verification_status == "verified"
    assert score.is_verified is True
    assert score.reviewed_by_id == organiser.id
    assert score.reviewed_at is not None


def test_owner_can_reject_a_pending_score(db):
    match, organiser = _make_match(db)
    score = _make_score(db, match)

    response = _review(match, organiser, "rejected")

    assert response.status_code == 200
    data = response.json()
    assert data["verification_status"] == "rejected"
    assert data["is_verified"] is False
    assert data["reviewed_by_id"] == organiser.id
    assert data["reviewed_at"] is not None

    db.refresh(score)
    assert score.verification_status == "rejected"
    assert score.is_verified is False


def test_a_newly_submitted_score_starts_as_pending(db):
    match, _ = _make_match(db)
    official = _make_user(db, "scorer")
    _assign(db, match, official)

    response = client.post(
        f"/matches/{match.id}/score",
        json={"match_id": match.id, "team_a_score": 1, "team_b_score": 0},
        headers=_auth_header(official),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["verification_status"] == "pending"
    assert data["is_verified"] is False
    assert data["reviewed_by_id"] is None
    assert data["reviewed_at"] is None


# --- Reviewing: who may review ---

def test_organiser_who_does_not_own_the_tournament_cannot_review(db):
    match, _ = _make_match(db)
    other_organiser = _make_user(db, "organiser")
    score = _make_score(db, match)

    response = _review(match, other_organiser, "verified")

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "You do not own this tournament"
    db.refresh(score)
    assert score.verification_status == "pending"
    assert score.reviewed_by_id is None


@pytest.mark.parametrize("role", ["scorer", "official", "player", "spectator"])
def test_other_roles_cannot_review_a_score(db, role):
    match, _ = _make_match(db)
    user = _make_user(db, role)
    score = _make_score(db, match)

    response = _review(match, user, "verified")

    assert response.status_code == 403
    db.refresh(score)
    assert score.verification_status == "pending"


def test_assigned_official_cannot_review_their_own_score(db):
    match, _ = _make_match(db)
    official = _make_user(db, "scorer")
    _assign(db, match, official)
    score = _make_score(db, match)

    response = _review(match, official, "verified")

    assert response.status_code == 403
    db.refresh(score)
    assert score.verification_status == "pending"


def test_review_without_a_token_is_rejected(db):
    match, _ = _make_match(db)
    _make_score(db, match)

    response = client.patch(
        f"/matches/{match.id}/score/verification", json={"status": "verified"}
    )

    assert response.status_code == 401


def test_review_of_an_unknown_match_returns_404(db):
    organiser = _make_user(db, "organiser")

    response = client.patch(
        "/matches/999999/score/verification",
        json={"status": "verified"},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 404


def test_review_with_no_score_submitted_returns_404(db):
    match, organiser = _make_match(db)

    response = _review(match, organiser, "verified")

    assert response.status_code == 404
    assert "No score" in response.json()["error"]["message"]


# --- Reviewing: validation and rules ---

@pytest.mark.parametrize(
    "body",
    [
        {"status": "pending"},
        {"status": "approved"},
        {},
        {"status": "verified", "reviewed_by_id": 1},
    ],
)
def test_invalid_decision_is_rejected(db, body):
    match, organiser = _make_match(db)
    score = _make_score(db, match)

    response = client.patch(
        f"/matches/{match.id}/score/verification",
        json=body,
        headers=_auth_header(organiser),
    )

    assert response.status_code == 422
    db.refresh(score)
    assert score.verification_status == "pending"


@pytest.mark.parametrize(
    "current,decision",
    [
        ("verified", "verified"),
        ("verified", "rejected"),
        ("rejected", "verified"),
        ("rejected", "rejected"),
    ],
)
def test_invalid_transitions_are_rejected_and_leave_the_score_unchanged(
    db, current, decision
):
    match, organiser = _make_match(db)
    reviewed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    score = _make_score(
        db,
        match,
        verification_status=current,
        reviewed_by_id=organiser.id,
        reviewed_at=reviewed_at,
    )

    response = _review(match, organiser, decision)

    assert response.status_code == 409
    assert "cannot be marked" in response.json()["error"]["message"]
    db.refresh(score)
    assert score.verification_status == current
    assert score.reviewed_at == reviewed_at


@pytest.mark.parametrize("status", ["scheduled", "cancelled", "completed"])
def test_score_can_only_be_reviewed_while_the_match_is_live(db, status):
    match, organiser = _make_match(db, status=status)
    score = _make_score(db, match)

    response = _review(match, organiser, "verified")

    assert response.status_code == 409
    assert "live" in response.json()["error"]["message"]
    db.refresh(score)
    assert score.verification_status == "pending"


def test_score_cannot_be_reviewed_without_both_teams(db):
    match, organiser = _make_match(db, with_teams=False)
    score = _make_score(db, match)

    response = _review(match, organiser, "verified")

    assert response.status_code == 400
    db.refresh(score)
    assert score.verification_status == "pending"


# --- Interaction with score updates (SCRUM-144) ---

def test_rejected_score_returns_to_pending_when_the_official_corrects_it(db):
    match, organiser = _make_match(db)
    official = _make_user(db, "scorer")
    _assign(db, match, official)
    _make_score(
        db,
        match,
        verification_status="rejected",
        reviewed_by_id=organiser.id,
        reviewed_at=datetime.now(timezone.utc),
    )

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 3},
        headers=_auth_header(official),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verification_status"] == "pending"
    assert data["is_verified"] is False
    assert data["reviewed_by_id"] is None
    assert data["reviewed_at"] is None

    assert _review(match, organiser, "verified").status_code == 200


def test_a_verified_score_can_no_longer_be_edited(db):
    match, organiser = _make_match(db)
    official = _make_user(db, "scorer")
    _assign(db, match, official)
    score = _make_score(db, match, team_a_score=2, team_b_score=1)

    assert _review(match, organiser, "verified").status_code == 200

    response = client.patch(
        f"/matches/{match.id}/score",
        json={"team_a_score": 9},
        headers=_auth_header(official),
    )

    assert response.status_code == 409
    assert "Finalized" in response.json()["error"]["message"]
    db.refresh(score)
    assert score.team_a_score == 2


# --- State rules and database guarantees ---

def test_verified_is_a_final_state():
    assert ALLOWED_TRANSITIONS["verified"] == set()


def test_rejected_scores_can_only_return_to_pending():
    assert ALLOWED_TRANSITIONS["rejected"] == {"pending"}


def test_unknown_current_state_has_no_valid_transitions():
    with pytest.raises(ConflictException):
        ensure_transition_allowed("bogus", "verified")


def test_database_rejects_an_inconsistent_verification_state(db):
    match, _ = _make_match(db)
    db.add(
        Score(
            match_id=match.id,
            team_a_score=0,
            team_b_score=0,
            is_verified=True,
            verification_status="pending",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_database_rejects_an_unknown_verification_status(db):
    match, _ = _make_match(db)
    db.add(
        Score(
            match_id=match.id,
            team_a_score=0,
            team_b_score=0,
            is_verified=False,
            verification_status="approved",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()

# --- Prevent disputed result finalization (SCRUM-159) ---

@pytest.mark.parametrize(
    "dispute_status",
    ["pending", "under_review"],
)
def test_unresolved_dispute_blocks_score_verification(
    db,
    dispute_status,
):
    match, organiser = _make_match(db)
    score = _make_score(db, match)
    complainant = _make_user(db, "player")

    dispute = Dispute(
        match_id=match.id,
        user_id=complainant.id,
        reason="The reported match score is incorrect.",
        status=dispute_status,
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = _review(match, organiser, "verified")

    assert response.status_code == 409

    message = response.json()["error"]["message"]
    assert f"ID={dispute.id}" in message
    assert f"status={dispute_status}" in message
    assert "The reported match score is incorrect." in message

    db.refresh(score)
    assert score.verification_status == "pending"
    assert score.is_verified is False
    assert score.reviewed_by_id is None
    assert score.reviewed_at is None


@pytest.mark.parametrize(
    "dispute_status",
    ["resolved", "rejected"],
)
def test_closed_dispute_does_not_block_score_verification(
    db,
    dispute_status,
):
    match, organiser = _make_match(db)
    score = _make_score(db, match)
    complainant = _make_user(db, "player")

    dispute = Dispute(
        match_id=match.id,
        user_id=complainant.id,
        reason="The result was disputed and reviewed.",
        status=dispute_status,
        resolution="The complaint has received a final decision.",
    )
    db.add(dispute)
    db.commit()

    response = _review(match, organiser, "verified")

    assert response.status_code == 200
    assert response.json()["verification_status"] == "verified"
    assert response.json()["is_verified"] is True

    db.refresh(score)
    assert score.verification_status == "verified"
    assert score.is_verified is True