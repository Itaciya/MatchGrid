from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import OfficialAssignment
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def _make_user(db, **overrides):
    defaults = dict(
        email=f"constraint_test_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    db.flush()
    return user


def _make_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"Constraint Test Tournament {uuid4()}",
        description="Test tournament",
        format="knockout",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )
    db.add(tournament)
    db.flush()
    return tournament


def _make_team(db, captain_id, **overrides):
    defaults = dict(
        name=f"Constraint Test Team {uuid4()}",
        captain_id=captain_id,
    )
    defaults.update(overrides)
    team = Team(**defaults)
    db.add(team)
    db.flush()
    return team


def _make_match(db, tournament_id, team_a_id, team_b_id):
    match = Match(
        tournament_id=tournament_id,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        scheduled_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        status="scheduled",
    )
    db.add(match)
    db.flush()
    return match


def test_duplicate_official_assignment_is_rejected(db):
    user = _make_user(db)
    official = _make_user(db, role="official")
    tournament = _make_tournament(db, organizer_id=user.id)
    team_a = _make_team(db, captain_id=user.id)
    team_b = _make_team(db, captain_id=user.id)
    match = _make_match(db, tournament.id, team_a.id, team_b.id)

    first_assignment = OfficialAssignment(
        match_id=match.id,
        official_id=official.id,
        assignment_type="referee",
    )
    db.add(first_assignment)
    db.commit()

    duplicate_assignment = OfficialAssignment(
        match_id=match.id,
        official_id=official.id,
        assignment_type="referee",
    )
    db.add(duplicate_assignment)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_official_can_hold_different_roles_on_same_match(db):
    user = _make_user(db)
    official = _make_user(db, role="official")
    tournament = _make_tournament(db, organizer_id=user.id)
    team_a = _make_team(db, captain_id=user.id)
    team_b = _make_team(db, captain_id=user.id)
    match = _make_match(db, tournament.id, team_a.id, team_b.id)

    referee_assignment = OfficialAssignment(
        match_id=match.id,
        official_id=official.id,
        assignment_type="referee",
    )
    var_assignment = OfficialAssignment(
        match_id=match.id,
        official_id=official.id,
        assignment_type="var",
    )

    db.add_all([referee_assignment, var_assignment])
    db.commit()

    assert referee_assignment.id is not None
    assert var_assignment.id is not None

    db.rollback()


def test_match_team_a_cannot_equal_team_b(db):
    user = _make_user(db)
    tournament = _make_tournament(db, organizer_id=user.id)
    team = _make_team(db, captain_id=user.id)

    match = Match(
        tournament_id=tournament.id,
        team_a_id=team.id,
        team_b_id=team.id,
        scheduled_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        status="scheduled",
    )
    db.add(match)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
