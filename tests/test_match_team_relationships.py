from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def create_test_user(db, prefix="match_relationship"):
    user = User(
        email=f"{prefix}_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()
    return user


def create_test_team(db, user, prefix):
    team = Team(
        name=f"{prefix} {uuid4()}",
        captain_id=user.id,
    )
    db.add(team)
    db.flush()
    return team


def create_test_tournament(db, user):
    tournament = Tournament(
        name=f"Match Relationship Tournament {uuid4()}",
        description="Test tournament for SCRUM-38",
        format="league",
        start_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 30, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=user.id,
    )
    db.add(tournament)
    db.flush()
    return tournament


def test_match_team_relationship(db):
    user = create_test_user(db)

    team_a = create_test_team(db, user, "Match Team A")
    team_b = create_test_team(db, user, "Match Team B")
    tournament = create_test_tournament(db, user)

    match = Match(
        tournament_id=tournament.id,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
        status="scheduled",
    )

    db.add(match)
    db.commit()

    # Match identifies both participating teams.
    assert match.id is not None
    assert match.team_a_id == team_a.id
    assert match.team_b_id == team_b.id

    # ORM relationships point to the correct Team objects.
    assert match.team_a.id == team_a.id
    assert match.team_b.id == team_b.id

    # A Team can retrieve its match history.
    assert match in team_a.home_matches
    assert match in team_b.away_matches

    db.rollback()


def test_match_with_invalid_team_reference_is_rejected(db):
    user = create_test_user(db)

    team = create_test_team(db, user, "Valid Match Team")
    tournament = create_test_tournament(db, user)

    match = Match(
        tournament_id=tournament.id,
        team_a_id=team.id,
        team_b_id=999999999,
        scheduled_at=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
        status="scheduled",
    )

    db.add(match)

    # Invalid team foreign-key reference must be rejected.
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()