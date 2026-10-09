import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundException
from app.core.security import hash_password
from app.main import app
from app.modules.dispute.models.dispute import Dispute
from app.modules.dispute.schemas.dispute import DisputeResolutionRequest
from app.modules.dispute.services.dispute_service import resolve_dispute
from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.score.models.score import Score
from app.modules.score.services.score_verification_service import VERIFIED
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.services.standings_service import (
    calculate_tournament_standings,
)
from app.modules.tournament_team.models.tournament_team import TournamentTeam
from app.modules.user.models import User


client = TestClient(app)


def _make_tournament_with_teams(db):
    """Create an organiser, tournament, two teams and their memberships."""

    unique = uuid.uuid4().hex

    organiser = User(
        email=f"{unique}@test.com",
        password_hash=hash_password("correctpassword123"),
        role="organiser",
        is_active=True,
    )
    db.add(organiser)
    db.commit()
    db.refresh(organiser)

    tournament = Tournament(
        name=f"Standings Tournament {unique}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    team_a = Team(
        name=f"Standings Team A {unique}",
        captain_id=organiser.id,
        status=TeamStatus.ACTIVE,
    )
    team_b = Team(
        name=f"Standings Team B {unique}",
        captain_id=organiser.id,
        status=TeamStatus.ACTIVE,
    )
    db.add_all([team_a, team_b])
    db.commit()
    db.refresh(team_a)
    db.refresh(team_b)

    db.add_all(
        [
            TournamentTeam(
                tournament_id=tournament.id,
                team_id=team_a.id,
            ),
            TournamentTeam(
                tournament_id=tournament.id,
                team_id=team_b.id,
            ),
        ]
    )
    db.commit()

    return tournament, organiser, team_a, team_b


def _make_match_with_score(
    db,
    tournament,
    team_a,
    team_b,
    match_number=1,
    *,
    match_status="completed",
    score_status="verified",
    team_a_score=2,
    team_b_score=1,
):
    """Create a match and its score."""

    match = Match(
        tournament_id=tournament.id,
        match_number=match_number,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(
            2099, 1, 2, 10, 0, tzinfo=timezone.utc
        ),
        status=match_status,
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    score = Score(
        match_id=match.id,
        team_a_score=team_a_score,
        team_b_score=team_b_score,
        verification_status=score_status,
        is_verified=(score_status == VERIFIED),
    )
    db.add(score)
    db.commit()
    db.refresh(score)

    return match, score


def _standings_by_team(db, tournament_id):
    standings = calculate_tournament_standings(
        db=db,
        tournament_id=tournament_id,
    )
    return {row["team_id"]: row for row in standings}


def test_standings_include_only_completed_verified_scores(db):
    tournament, _, team_a, team_b = _make_tournament_with_teams(db)

    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        match_status="completed",
        score_status="verified",
        team_a_score=2,
        team_b_score=0,
    )

    # This score is not verified and must not affect standings.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=2,
        match_status="completed",
        score_status="pending",
        team_a_score=0,
        team_b_score=5,
    )

    # This match is not complete and must not affect standings.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=3,
        match_status="live",
        score_status="verified",
        team_a_score=0,
        team_b_score=4,
    )

    standings = _standings_by_team(db, tournament.id)

    assert standings[team_a.id]["played"] == 1
    assert standings[team_a.id]["wins"] == 1
    assert standings[team_a.id]["points"] == 3
    assert standings[team_a.id]["score_for"] == 2

    assert standings[team_b.id]["played"] == 1
    assert standings[team_b.id]["losses"] == 1
    assert standings[team_b.id]["points"] == 0


def test_standings_include_registered_teams_without_matches(db):
    tournament, _, team_a, team_b = _make_tournament_with_teams(db)

    standings = _standings_by_team(db, tournament.id)

    assert len(standings) == 2

    for team_id in (team_a.id, team_b.id):
        assert standings[team_id]["played"] == 0
        assert standings[team_id]["wins"] == 0
        assert standings[team_id]["draws"] == 0
        assert standings[team_id]["losses"] == 0
        assert standings[team_id]["points"] == 0


def test_standings_reflect_score_changes_after_dispute_resolution(db):
    tournament, organiser, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    match, score = _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_status="completed",
        score_status="verified",
        team_a_score=2,
        team_b_score=0,
    )

    before = _standings_by_team(db, tournament.id)

    assert before[team_a.id]["points"] == 3
    assert before[team_b.id]["points"] == 0

    dispute = Dispute(
        match_id=match.id,
        user_id=organiser.id,
        reason="The submitted score was incorrect",
        status="under_review",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    request = DisputeResolutionRequest(
        decision="resolved",
        resolution="Score corrected after review",
        corrected_team_a_score=0,
        corrected_team_b_score=2,
    )

    resolve_dispute(
        db=db,
        current_user_id=organiser.id,
        dispute_id=dispute.id,
        data=request,
    )

    db.refresh(score)
    db.refresh(match)
    db.refresh(dispute)

    assert score.team_a_score == 0
    assert score.team_b_score == 2
    assert score.verification_status == "verified"
    assert score.is_verified is True
    assert match.status == "completed"
    assert dispute.status == "resolved"

    after = _standings_by_team(db, tournament.id)

    assert after[team_a.id]["points"] == 0
    assert after[team_a.id]["losses"] == 1

    assert after[team_b.id]["points"] == 3
    assert after[team_b.id]["wins"] == 1


def test_standings_endpoint_returns_200(db):
    tournament, _, team_a, team_b = _make_tournament_with_teams(db)

    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_status="completed",
        score_status="verified",
        team_a_score=1,
        team_b_score=0,
    )

    response = client.get(
        f"/tournaments/{tournament.id}/standings"
    )

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert all("points" in row for row in data)
    assert all("rank" in row for row in data)


def test_standings_for_unknown_tournament_raise_not_found(db):
    with pytest.raises(NotFoundException):
        calculate_tournament_standings(
            db=db,
            tournament_id=999999999,
        )