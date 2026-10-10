import pytest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundException
from app.core.security import hash_password
from app.main import app
from app.modules.dispute.models.dispute import Dispute
from app.modules.dispute.schemas.dispute import DisputeResolutionRequest
from app.modules.dispute.services.dispute_service import resolve_dispute
from app.modules.match.models.match import Match
from app.modules.match.services.match_status_service import complete_match
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.score.models.score import Score
from app.modules.score.services.score_verification_service import (
    VERIFIED,
    review_score,
)
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
    """Return standings indexed by team ID."""

    standings = calculate_tournament_standings(
        db=db,
        tournament_id=tournament_id,
    )
    return {row["team_id"]: row for row in standings}


# ---------------------------------------------------------
# Finalized and verified results
# ---------------------------------------------------------

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

    # Unverified scores must not affect standings.
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

    # A live match must not affect finalized standings.
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


# ---------------------------------------------------------
# Recalculate standings after a corrected result
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Standings endpoint
# ---------------------------------------------------------

def test_standings_endpoint_returns_200_with_consistent_response(db):
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
    tournament.fixtures_published = True
    db.commit()

    response = client.get(
        f"/tournaments/{tournament.id}/standings"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    required_fields = {
        "rank",
        "team_id",
        "team_name",
        "played",
        "wins",
        "draws",
        "losses",
        "score_for",
        "score_against",
        "score_difference",
        "points",
    }

    for row in data:
        assert required_fields.issubset(row.keys())
        assert isinstance(row["rank"], int)
        assert isinstance(row["points"], int)
        assert isinstance(row["wins"], int)
        assert isinstance(row["draws"], int)
        assert isinstance(row["losses"], int)

    by_id = {row["team_id"]: row for row in data}

    assert by_id[team_a.id]["rank"] == 1
    assert by_id[team_a.id]["wins"] == 1
    assert by_id[team_a.id]["points"] == 3

    assert by_id[team_b.id]["rank"] == 2
    assert by_id[team_b.id]["losses"] == 1
    assert by_id[team_b.id]["points"] == 0


def test_standings_for_unknown_tournament_raise_not_found(db):
    with pytest.raises(NotFoundException):
        calculate_tournament_standings(
            db=db,
            tournament_id=999999999,
        )


def test_standings_endpoint_returns_404_for_unknown_tournament():
    response = client.get(
        "/tournaments/999999999/standings"
    )

    assert response.status_code == 404


# ---------------------------------------------------------
# Ranking and tie-break rules
# ---------------------------------------------------------

def test_standings_apply_ranking_tie_breakers(db):
    tournament, organiser, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    extra_teams = {}

    for label in ("C", "D", "E", "F"):
        team = Team(
            name=f"Standings Team {label} {uuid.uuid4().hex}",
            captain_id=organiser.id,
            status=TeamStatus.ACTIVE,
        )
        db.add(team)
        db.commit()
        db.refresh(team)

        db.add(
            TournamentTeam(
                tournament_id=tournament.id,
                team_id=team.id,
            )
        )
        db.commit()

        extra_teams[label] = team

    team_c = extra_teams["C"]
    team_d = extra_teams["D"]
    team_e = extra_teams["E"]
    team_f = extra_teams["F"]

    # Team A beats B: score difference +2.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        team_a_score=2,
        team_b_score=0,
    )

    # Team C beats D: score difference +2, higher score for.
    _make_match_with_score(
        db,
        tournament,
        team_c,
        team_d,
        match_number=2,
        team_a_score=5,
        team_b_score=3,
    )

    # Team E has a larger score difference than C.
    _make_match_with_score(
        db,
        tournament,
        team_e,
        team_f,
        match_number=3,
        team_a_score=4,
        team_b_score=0,
    )

    result = calculate_tournament_standings(
        db=db,
        tournament_id=tournament.id,
    )

    ranked_team_ids = [row["team_id"] for row in result]

    assert ranked_team_ids == [
        team_e.id,
        team_c.id,
        team_a.id,
        team_d.id,
        team_b.id,
        team_f.id,
    ]

    assert [row["rank"] for row in result] == [
        1, 2, 3, 4, 5, 6
    ]


def test_standings_ignore_negative_scores(db):
    tournament, _, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_status="completed",
        score_status="verified",
        team_a_score=-1,
        team_b_score=2,
    )

    standings = _standings_by_team(db, tournament.id)

    assert standings[team_a.id]["played"] == 0
    assert standings[team_a.id]["points"] == 0

    assert standings[team_b.id]["played"] == 0
    assert standings[team_b.id]["points"] == 0


def test_standings_break_complete_ties_by_team_name(db):
    tournament, _, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    result = calculate_tournament_standings(
        db=db,
        tournament_id=tournament.id,
    )

    assert result[0]["team_name"].casefold() <= (
        result[1]["team_name"].casefold()
    )

    assert result[0]["rank"] == 1
    assert result[1]["rank"] == 2


def test_standings_follow_configured_tie_break_order(db):
    tournament, organiser, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    unique = uuid.uuid4().hex

    team_c = Team(
        name=f"Standings Team C {unique}",
        captain_id=organiser.id,
        status=TeamStatus.ACTIVE,
    )
    team_d = Team(
        name=f"Standings Team D {unique}",
        captain_id=organiser.id,
        status=TeamStatus.ACTIVE,
    )

    db.add_all([team_c, team_d])
    db.commit()
    db.refresh(team_c)
    db.refresh(team_d)

    db.add_all(
        [
            TournamentTeam(
                tournament_id=tournament.id,
                team_id=team_c.id,
            ),
            TournamentTeam(
                tournament_id=tournament.id,
                team_id=team_d.id,
            ),
        ]
    )

    tournament.format_config = {
        "number_of_teams": 4,
        "tie_break_rules": [
            "score_for",
            "score_difference",
            "team_name",
        ],
    }
    db.commit()

    # Team A wins 5-4: 3 points, score for 5.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        team_a_score=5,
        team_b_score=4,
    )

    # Team C wins 2-0: 3 points, score for 2.
    _make_match_with_score(
        db,
        tournament,
        team_c,
        team_d,
        match_number=2,
        team_a_score=2,
        team_b_score=0,
    )

    standings = calculate_tournament_standings(
        db=db,
        tournament_id=tournament.id,
    )

    # Points tie, so configured score_for takes priority.
    assert standings[0]["team_id"] == team_a.id
    assert standings[0]["rank"] == 1

    assert standings[1]["team_id"] == team_c.id
    assert standings[1]["rank"] == 2


# ---------------------------------------------------------
# Cancelled and invalid matches
# ---------------------------------------------------------

def test_standings_ignore_cancelled_matches(db):
    tournament, _, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        match_status="cancelled",
        score_status="verified",
        team_a_score=5,
        team_b_score=0,
    )

    standings = _standings_by_team(db, tournament.id)

    for team_id in (team_a.id, team_b.id):
        assert standings[team_id]["played"] == 0
        assert standings[team_id]["wins"] == 0
        assert standings[team_id]["losses"] == 0
        assert standings[team_id]["points"] == 0


def test_invalid_draw_results_do_not_update_draw_counts(db):
    tournament, _, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    # An unverified draw must be ignored.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        match_status="completed",
        score_status="pending",
        team_a_score=1,
        team_b_score=1,
    )

    # A cancelled draw must also be ignored.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=2,
        match_status="cancelled",
        score_status="verified",
        team_a_score=3,
        team_b_score=3,
    )

    standings = _standings_by_team(db, tournament.id)

    for team_id in (team_a.id, team_b.id):
        assert standings[team_id]["played"] == 0
        assert standings[team_id]["draws"] == 0
        assert standings[team_id]["points"] == 0


# ---------------------------------------------------------
# Win/loss calculation and recalculation
# ---------------------------------------------------------

def test_win_loss_statistics_update_after_new_verified_result(db):
    tournament, _, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    # First finalized result: Team A wins.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        match_status="completed",
        score_status="verified",
        team_a_score=2,
        team_b_score=1,
    )

    first_standings = _standings_by_team(db, tournament.id)

    assert first_standings[team_a.id]["wins"] == 1
    assert first_standings[team_a.id]["losses"] == 0
    assert first_standings[team_b.id]["wins"] == 0
    assert first_standings[team_b.id]["losses"] == 1

    # Second finalized result: Team B wins.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=2,
        match_status="completed",
        score_status="verified",
        team_a_score=0,
        team_b_score=3,
    )

    updated_standings = _standings_by_team(db, tournament.id)

    assert updated_standings[team_a.id]["played"] == 2
    assert updated_standings[team_a.id]["wins"] == 1
    assert updated_standings[team_a.id]["losses"] == 1

    assert updated_standings[team_b.id]["played"] == 2
    assert updated_standings[team_b.id]["wins"] == 1
    assert updated_standings[team_b.id]["losses"] == 1


def test_valid_finalized_draw_updates_both_teams(db):
    tournament, _, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        match_status="completed",
        score_status="verified",
        team_a_score=2,
        team_b_score=2,
    )

    standings = _standings_by_team(db, tournament.id)

    assert standings[team_a.id]["played"] == 1
    assert standings[team_b.id]["played"] == 1

    assert standings[team_a.id]["draws"] == 1
    assert standings[team_b.id]["draws"] == 1

    assert standings[team_a.id]["points"] == 1
    assert standings[team_b.id]["points"] == 1

    assert standings[team_a.id]["wins"] == 0
    assert standings[team_b.id]["wins"] == 0
    assert standings[team_a.id]["losses"] == 0
    assert standings[team_b.id]["losses"] == 0


def test_standings_update_after_score_verification_and_completion(db):
    tournament, organiser, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    match, score = _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        match_status="live",
        score_status="pending",
        team_a_score=3,
        team_b_score=1,
    )

    # Pending results must not count.
    before = _standings_by_team(db, tournament.id)

    assert before[team_a.id]["played"] == 0
    assert before[team_b.id]["played"] == 0

    review_score(
        db=db,
        match_id=match.id,
        reviewer_id=organiser.id,
        decision="verified",
    )

    db.refresh(score)

    assert score.verification_status == "verified"
    assert score.is_verified is True

    # A verified score on a live match is not finalized yet.
    while_live = _standings_by_team(db, tournament.id)

    assert while_live[team_a.id]["played"] == 0
    assert while_live[team_b.id]["played"] == 0

    complete_match(db, match.id)

    db.refresh(match)
    assert match.status == "completed"

    updated = _standings_by_team(db, tournament.id)

    assert updated[team_a.id]["played"] == 1
    assert updated[team_a.id]["wins"] == 1
    assert updated[team_a.id]["points"] == 3

    assert updated[team_b.id]["played"] == 1
    assert updated[team_b.id]["losses"] == 1
    assert updated[team_b.id]["points"] == 0


# ---------------------------------------------------------
# Configurable scoring rules
# ---------------------------------------------------------

def test_standings_use_custom_scoring_rules_and_cumulative_points(db):
    tournament, _, team_a, team_b = (
        _make_tournament_with_teams(db)
    )

    tournament.format_config = {
        "number_of_teams": 2,
        "points_per_win": 5,
        "points_per_draw": 2,
        "points_per_loss": 1,
    }
    db.commit()

    # Team A wins: 5 points for A, 1 for B.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=1,
        team_a_score=2,
        team_b_score=1,
    )

    # Draw: both receive 2 additional points.
    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_number=2,
        team_a_score=1,
        team_b_score=1,
    )

    standings = _standings_by_team(db, tournament.id)

    assert standings[team_a.id]["played"] == 2
    assert standings[team_a.id]["wins"] == 1
    assert standings[team_a.id]["draws"] == 1
    assert standings[team_a.id]["points"] == 7

    assert standings[team_b.id]["played"] == 2
    assert standings[team_b.id]["losses"] == 1
    assert standings[team_b.id]["draws"] == 1
    assert standings[team_b.id]["points"] == 3

def test_public_leaderboard_returns_published_standings_without_login(db):
    tournament, _, team_a, team_b = _make_tournament_with_teams(db)

    tournament.fixtures_published = True
    db.commit()

    _make_match_with_score(
        db,
        tournament,
        team_a,
        team_b,
        match_status="completed",
        score_status="verified",
        team_a_score=2,
        team_b_score=0,
    )

    # No authentication header: the endpoint is public.
    response = client.get(
        f"/tournaments/{tournament.id}/leaderboard"
    )

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert data[0]["team_id"] == team_a.id
    assert data[0]["rank"] == 1
    assert data[0]["wins"] == 1
    assert data[0]["points"] == 3


def test_public_leaderboard_hides_unpublished_tournament(db):
    tournament, _, _, _ = _make_tournament_with_teams(db)

    assert tournament.fixtures_published is False

    response = client.get(
        f"/tournaments/{tournament.id}/leaderboard"
    )

    assert response.status_code == 404