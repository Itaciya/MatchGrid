from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def _make_user(db):
    user = User(
        email=f"tournament_match_relationship_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()
    return user


def _make_tournament(db, organizer_id, **overrides):
    defaults = dict(
        name=f"Tournament Match Relationship Test Tournament {uuid4()}",
        description="Test tournament",
        format="knockout",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )
    defaults.update(overrides)
    tournament = Tournament(**defaults)
    db.add(tournament)
    db.flush()
    return tournament


def _make_team(db, captain_id, **overrides):
    defaults = dict(
        name=f"Tournament Match Relationship Test Team {uuid4()}",
        captain_id=captain_id,
    )
    defaults.update(overrides)
    team = Team(**defaults)
    db.add(team)
    db.flush()
    return team


def test_tournament_match_relationship(db):
    user = _make_user(db)
    tournament = _make_tournament(db, organizer_id=user.id)
    team_a = _make_team(db, captain_id=user.id)
    team_b = _make_team(db, captain_id=user.id)

    match = Match(
        tournament_id=tournament.id,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        status="scheduled",
    )

    db.add(match)
    db.commit()

    assert match.id is not None
    assert match.tournament_id == tournament.id
    assert match.tournament == tournament

    db.rollback()


def test_tournament_can_retrieve_its_matches(db):
    user = _make_user(db)
    tournament = _make_tournament(db, organizer_id=user.id)
    team_a = _make_team(db, captain_id=user.id)
    team_b = _make_team(db, captain_id=user.id)

    match_one = Match(
        tournament_id=tournament.id,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        status="scheduled",
    )
    match_two = Match(
        tournament_id=tournament.id,
        team_a_id=team_b.id,
        team_b_id=team_a.id,
        scheduled_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        status="scheduled",
    )

    db.add_all([match_one, match_two])
    db.commit()
    db.refresh(tournament)

    retrieved_ids = {m.id for m in tournament.matches}
    assert retrieved_ids == {match_one.id, match_two.id}

    db.rollback()


def test_invalid_tournament_reference_is_rejected(db):
    user = _make_user(db)
    team_a = _make_team(db, captain_id=user.id)
    team_b = _make_team(db, captain_id=user.id)

    nonexistent_tournament_id = 2_147_483_647

    match = Match(
        tournament_id=nonexistent_tournament_id,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        status="scheduled",
    )

    db.add(match)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
