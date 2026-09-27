from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament_team.models.tournament_team import TournamentTeam
from app.modules.user.models import User


def test_team_tournament_relationship(db):
    user = User(
        email=f"tournament_relationship_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()

    team = Team(
        name=f"Tournament Relationship Test Team {uuid4()}",
        captain_id=user.id,
    )

    tournament = Tournament(
        name=f"Relationship Test Tournament {uuid4()}",
        description="Test tournament",
        format="knockout",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=user.id,
    )

    db.add_all([team, tournament])
    db.flush()

    tournament_team = TournamentTeam(
        tournament_id=tournament.id,
        team_id=team.id,
    )

    db.add(tournament_team)
    db.commit()

    assert tournament_team.id is not None
    assert tournament_team.tournament_id == tournament.id
    assert tournament_team.team_id == team.id

    db.rollback()


def test_duplicate_team_tournament_relationship_is_rejected(db):
    user = User(
        email=f"duplicate_relationship_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()

    team = Team(
        name=f"Duplicate Relationship Test Team {uuid4()}",
        captain_id=user.id,
    )

    tournament = Tournament(
        name=f"Duplicate Relationship Test Tournament {uuid4()}",
        description="Test tournament",
        format="league",
        start_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 2, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=user.id,
    )

    db.add_all([team, tournament])
    db.flush()

    first_relationship = TournamentTeam(
        tournament_id=tournament.id,
        team_id=team.id,
    )

    db.add(first_relationship)
    db.commit()

    duplicate_relationship = TournamentTeam(
        tournament_id=tournament.id,
        team_id=team.id,
    )

    db.add(duplicate_relationship)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()