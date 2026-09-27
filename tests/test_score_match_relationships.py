from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.modules.user.models import User
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.match.models.match import Match
from app.modules.score.models.score import Score


def create_score_match_data(db):
    user = User(
        email=f"score_match_{uuid4()}@example.com",
        password_hash="test_hash",
        role="organizer",
    )
    db.add(user)
    db.flush()

    team_a = Team(
        name=f"Score Team A {uuid4()}",
        captain_id=user.id,
        status="active",
    )
    team_b = Team(
        name=f"Score Team B {uuid4()}",
        captain_id=user.id,
        status="active",
    )
    db.add_all([team_a, team_b])
    db.flush()

    tournament = Tournament(
        name=f"Score Tournament {uuid4()}",
        description="SCRUM-39 test tournament",
        format="single_elimination",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc),
        status="upcoming",
        organizer_id=user.id,
    )
    db.add(tournament)
    db.flush()

    match = Match(
        tournament_id=tournament.id,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )
    db.add(match)
    db.flush()

    return match


def test_score_belongs_to_correct_match(db):
    match = create_score_match_data(db)

    score = Score(
        match_id=match.id,
        team_a_score=2,
        team_b_score=1,
        is_verified=False,
    )
    db.add(score)
    db.commit()

    db.refresh(match)

    assert match.score is not None
    assert match.score.id == score.id
    assert match.score.match_id == match.id


def test_match_retrieves_its_score(db):
    match = create_score_match_data(db)

    score = Score(
        match_id=match.id,
        team_a_score=3,
        team_b_score=2,
        is_verified=True,
    )
    db.add(score)
    db.commit()

    db.refresh(score)

    assert score.match is not None
    assert score.match.id == match.id


def test_invalid_match_reference_for_score_is_rejected(db):
    score = Score(
        match_id=999999999,
        team_a_score=0,
        team_b_score=0,
        is_verified=False,
    )
    db.add(score)

    try:
        db.commit()
        assert False, "Invalid match_id was accepted"
    except IntegrityError:
        db.rollback()
