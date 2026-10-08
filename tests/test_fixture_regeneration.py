import uuid
from datetime import date, datetime, time, timezone

import pytest

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.match.services.fixture_regeneration_service import (
    regenerate_round_robin_fixtures,
)
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import (
    RegistrationStatus,
    RegistrationType,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.modules.venue.models.venue import Venue


def create_user(db):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash="hash",
        role="captain",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_tournament(db, user_id):
    tournament = Tournament(
        name=f"Regeneration Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(
            2099,
            1,
            1,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        end_date=datetime(
            2099,
            1,
            10,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        status="upcoming",
        organizer_id=user_id,
    )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    return tournament


def create_team(db, captain_id):
    team = Team(
        name=f"Regenerate Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )

    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def create_venue(db):
    venue = Venue(
        name=f"Regeneration Venue {uuid.uuid4()}",
        location="Dhaka",
        description="Test venue",
        capacity=5000,
    )

    db.add(venue)
    db.commit()
    db.refresh(venue)

    return venue


def approve_registration(db, tournament_id, team_id):
    registration = Registration(
        tournament_id=tournament_id,
        team_id=team_id,
        registration_type=RegistrationType.TEAM.value,
        status=RegistrationStatus.APPROVED.value,
    )

    db.add(registration)
    db.commit()


def setup_fixture(db):
    user = create_user(db)

    tournament = create_tournament(
        db,
        user.id,
    )

    teams = [
        create_team(db, user.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_registration(
            db,
            tournament.id,
            team.id,
        )

    return tournament, teams


def test_regenerate_removes_old_scheduled_fixtures(db):
    tournament, teams = setup_fixture(db)

    first_generation = regenerate_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[team.id for team in teams],
        fixture_date=date(2099, 1, 2),
        fixture_time=time(10, 0),
    )

    assert len(first_generation) == 6

    second_generation = regenerate_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[team.id for team in teams],
        fixture_date=date(2099, 1, 3),
        fixture_time=time(10, 0),
    )

    assert len(second_generation) == 6

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament.id
        )
        .all()
    )

    assert len(matches) == 6

    assert all(
        match.scheduled_at.date() == date(2099, 1, 3)
        for match in matches
    )


def test_regeneration_blocked_after_completed_match(db):
    tournament, teams = setup_fixture(db)

    matches = regenerate_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[team.id for team in teams],
        fixture_date=date(2099, 1, 2),
        fixture_time=time(10, 0),
    )

    matches[0].status = "completed"
    db.commit()

    with pytest.raises(BadRequestException):
        regenerate_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[team.id for team in teams],
            fixture_date=date(2099, 1, 3),
            fixture_time=time(10, 0),
        )


def test_regeneration_rolls_back_when_new_fixture_generation_fails(
    db,
):
    tournament, teams = setup_fixture(db)
    venue = create_venue(db)

    first_generation = regenerate_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[team.id for team in teams],
        fixture_date=date(2099, 1, 2),
        fixture_time=time(10, 0),
        venue_id=venue.id,
    )

    assert len(first_generation) == 6

    original_match_ids = {
        match.id
        for match in first_generation
    }

    original_schedule = {
        match.id: match.scheduled_at
        for match in first_generation
    }

    with pytest.raises(
        NotFoundException,
        match="Venue not found",
    ):
        regenerate_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[team.id for team in teams],
            fixture_date=date(2099, 1, 3),
            fixture_time=time(10, 0),
            venue_id=999999,
        )

    remaining_matches = (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament.id
        )
        .all()
    )

    assert len(remaining_matches) == 6

    remaining_match_ids = {
        match.id
        for match in remaining_matches
    }

    assert remaining_match_ids == original_match_ids

    for match in remaining_matches:
        assert (
            match.scheduled_at
            == original_schedule[match.id]
        )
        assert match.status == "scheduled"