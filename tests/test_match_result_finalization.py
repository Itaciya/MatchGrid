import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.player_team.models.team import Team, TeamStatus
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


def _make_match(db, with_teams=True):
    organiser = _make_user(db, "organiser")

    tournament = Tournament(
        name=f"Result Test Tournament {uuid.uuid4()}",
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
        team_a = Team(
            name=f"Result Team A {uuid.uuid4()}",
            captain_id=organiser.id,
            status=TeamStatus.ACTIVE,
        )
        team_b = Team(
            name=f"Result Team B {uuid.uuid4()}",
            captain_id=organiser.id,
            status=TeamStatus.ACTIVE,
        )
        db.add_all([team_a, team_b])
        db.commit()
        db.refresh(team_a)
        db.refresh(team_b)
        team_a_id, team_b_id = team_a.id, team_b.id

    match = Match(
        tournament_id=tournament.id,
        match_number=1,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        scheduled_at=datetime(
            2099, 1, 2, 10, 0, tzinfo=timezone.utc
        ),
        status="live",
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    return match, organiser


def _make_score(
    db,
    match,
    verification_status="verified",
    team_a_score=2,
    team_b_score=1,
):
    score = Score(
        match_id=match.id,
        team_a_score=team_a_score,
        team_b_score=team_b_score,
        verification_status=verification_status,
        is_verified=(verification_status == "verified"),
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


def _finalize(match, user):
    return client.post(
        f"/matches/{match.id}/result/finalize",
        headers=_auth_header(user),
    )


def test_organiser_can_finalize_a_verified_score(db):
    match, organiser = _make_match(db)
    score = _make_score(db, match, team_a_score=3, team_b_score=1)

    response = _finalize(match, organiser)

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["match_id"] == match.id
    assert data["outcome"] == "team_a_win"
    assert data["winner_team_id"] == match.team_a_id
    assert data["loser_team_id"] == match.team_b_id
    assert data["team_a_score"] == 3
    assert data["team_b_score"] == 1
    assert data["finalized_by_id"] == organiser.id

    db.refresh(match)
    assert match.status == "completed"

    result = db.query(MatchResult).filter_by(match_id=match.id).one()
    assert result.id == data["id"]
    assert result.finalized_by_id == organiser.id

    db.refresh(score)
    assert score.verification_status == "verified"


@pytest.mark.parametrize("verification_status", ["pending", "rejected"])
def test_unverified_score_cannot_be_finalized(db, verification_status):
    match, organiser = _make_match(db)
    _make_score(db, match, verification_status=verification_status)

    response = _finalize(match, organiser)

    assert response.status_code == 409, response.text
    assert db.query(MatchResult).filter_by(match_id=match.id).count() == 0

    db.refresh(match)
    assert match.status == "live"


def test_match_cannot_be_finalized_twice(db):
    match, organiser = _make_match(db)
    _make_score(db, match)

    first_response = _finalize(match, organiser)
    assert first_response.status_code == 201, first_response.text

    second_response = _finalize(match, organiser)

    assert second_response.status_code == 409, second_response.text
    assert db.query(MatchResult).filter_by(match_id=match.id).count() == 1


def test_another_organiser_cannot_finalize_the_result(db):
    match, _ = _make_match(db)
    other_organiser = _make_user(db, "organiser")
    _make_score(db, match)

    response = _finalize(match, other_organiser)

    assert response.status_code == 403, response.text
    assert db.query(MatchResult).filter_by(match_id=match.id).count() == 0

    db.refresh(match)
    assert match.status == "live"


@pytest.mark.parametrize(
    "role",
    ["scorer", "official", "player", "spectator"],
)
def test_non_organiser_cannot_finalize_a_result(db, role):
    match, _ = _make_match(db)
    user = _make_user(db, role)
    _make_score(db, match)

    response = _finalize(match, user)

    assert response.status_code == 403, response.text
    assert db.query(MatchResult).filter_by(match_id=match.id).count() == 0


def test_finalization_requires_a_submitted_score(db):
    match, organiser = _make_match(db)

    response = _finalize(match, organiser)

    assert response.status_code == 404, response.text
    assert db.query(MatchResult).filter_by(match_id=match.id).count() == 0

    db.refresh(match)
    assert match.status == "live"


def test_finalization_requires_both_teams(db):
    match, organiser = _make_match(db, with_teams=False)
    _make_score(db, match)

    response = _finalize(match, organiser)

    assert response.status_code == 400, response.text
    assert db.query(MatchResult).filter_by(match_id=match.id).count() == 0

    db.refresh(match)
    assert match.status == "live"


def test_draw_finalization_has_no_winner_or_loser(db):
    match, organiser = _make_match(db)
    _make_score(db, match, team_a_score=2, team_b_score=2)

    response = _finalize(match, organiser)

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["outcome"] == "draw"
    assert data["winner_team_id"] is None
    assert data["loser_team_id"] is None


def test_unauthenticated_user_cannot_finalize(db):
    match, _ = _make_match(db)
    _make_score(db, match)

    response = client.post(f"/matches/{match.id}/result/finalize")

    assert response.status_code in (401, 403)
    assert db.query(MatchResult).filter_by(match_id=match.id).count() == 0
