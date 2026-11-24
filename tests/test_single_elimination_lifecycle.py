"""End-to-end single-elimination lifecycle: byes, advancement, draws and
tournament completion, played through the real services."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.match.models.match import Match
from app.modules.match.services.match_result_service import (
    correct_match_result,
    finalize_match_result,
)
from app.modules.match.services.match_start_service import start_match
from app.modules.match.services.match_status_service import complete_match
from app.modules.match.services.single_elimination_service import (
    create_single_elimination_bracket,
)
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.score.schemas.score import ScoreCreate
from app.modules.score.services.score_service import create_score
from app.modules.score.services.score_verification_service import review_score
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def _user(db, role):
    user = User(
        email=f"se_lifecycle_{uuid4()}@example.com",
        password_hash="not-used",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _tournament_with_teams(db, team_count):
    organiser = _user(db, "organiser")
    tournament = Tournament(
        name=f"SE Lifecycle {uuid4()}",
        format="single_elimination",
        participation_type="team",
        start_date=datetime(2099, 3, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 3, 10, tzinfo=timezone.utc),
        registration_open_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        registration_close_at=datetime(2099, 2, 1, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()

    teams = []
    for _ in range(team_count):
        team = Team(
            name=f"SE Team {uuid4()}",
            captain_id=_user(db, "player").id,
            status=TeamStatus.ACTIVE,
        )
        db.add(team)
        db.commit()
        db.add(
            Registration(
                tournament_id=tournament.id,
                team_id=team.id,
                registration_type="team",
                status="approved",
            )
        )
        db.commit()
        teams.append(team)

    return organiser, tournament, teams


def _play(db, match, organiser, team_a_score, team_b_score):
    start_match(db, match.id)
    create_score(
        db,
        match.id,
        ScoreCreate(
            match_id=match.id,
            team_a_score=team_a_score,
            team_b_score=team_b_score,
        ),
    )
    review_score(db, match.id, organiser.id, "verified")
    complete_match(db, match.id)
    return finalize_match_result(db, match.id, organiser.id)


def _matches(db, tournament):
    return (
        db.query(Match)
        .filter(Match.tournament_id == tournament.id)
        .order_by(Match.match_number)
        .all()
    )


def test_three_team_bracket_marks_bye_and_completes_tournament(db):
    organiser, tournament, teams = _tournament_with_teams(db, 3)

    create_single_elimination_bracket(db, tournament)
    semi_1, semi_2, final = _matches(db, tournament)

    # Seeds 1v4 (bye) and 2v3: the bye match is never played.
    statuses = sorted([semi_1.status, semi_2.status])
    assert statuses == ["bye", "scheduled"]

    playable = semi_1 if semi_1.status == "scheduled" else semi_2
    bye_match = semi_2 if playable is semi_1 else semi_1
    bye_team = bye_match.team_a_id or bye_match.team_b_id

    _play(db, playable, organiser, 3, 1)
    db.refresh(final)

    assert final.team_a_id is not None
    assert final.team_b_id is not None
    assert bye_team in (final.team_a_id, final.team_b_id)

    _play(db, final, organiser, 2, 0)

    db.refresh(tournament)
    assert tournament.status == "completed"


def test_winner_is_placed_by_bracket_position_not_finish_order(db):
    organiser, tournament, teams = _tournament_with_teams(db, 4)

    create_single_elimination_bracket(db, tournament)
    first, second, final = _matches(db, tournament)

    # Finish the second semi first: its winner must still go to team B.
    second_result = _play(db, second, organiser, 1, 0)
    db.refresh(final)
    assert final.team_a_id is None
    assert final.team_b_id == second_result.winner_team_id

    first_result = _play(db, first, organiser, 0, 4)
    db.refresh(final)
    assert final.team_a_id == first_result.winner_team_id


def test_knockout_draw_cannot_be_finalized(db):
    organiser, tournament, _ = _tournament_with_teams(db, 2)

    create_single_elimination_bracket(db, tournament)
    (final,) = _matches(db, tournament)

    with pytest.raises(ConflictException):
        _play(db, final, organiser, 1, 1)

    db.refresh(final)
    assert final.status == "completed"
    db.refresh(tournament)
    assert tournament.status == "ongoing"


def test_correcting_a_semi_final_swaps_the_finalist(db):
    organiser, tournament, _ = _tournament_with_teams(db, 4)

    create_single_elimination_bracket(db, tournament)
    first, _, final = _matches(db, tournament)

    original_winner = _play(db, first, organiser, 2, 1).winner_team_id
    db.refresh(final)
    assert final.team_a_id == original_winner

    corrected = correct_match_result(
        db, first.id, organiser.id, 1, 2, "Scores were entered the wrong way round"
    )

    db.refresh(final)
    assert corrected.winner_team_id != original_winner
    assert final.team_a_id == corrected.winner_team_id
