import uuid
from datetime import date, datetime, time, timezone

import pytest

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.match.services.fixture_service import (
    create_round_robin_fixtures,
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
        password_hash="test_password_hash",
        role="captain",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_tournament(
    db,
    organizer_id,
    tournament_format="round_robin",
):
    tournament = Tournament(
        name=f"Fixture Generation Tournament {uuid.uuid4()}",
        format=tournament_format,
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
        organizer_id=organizer_id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def create_team(db, captain_id):
    team = Team(
        name=f"Generation Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def create_venue(db):
    venue = Venue(
        name=f"Generation Venue {uuid.uuid4()}",
        location="Dhaka",
        description="Test venue",
        capacity=5000,
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def approve_team_registration(db, tournament_id, team_id):
    registration = Registration(
        tournament_id=tournament_id,
        team_id=team_id,
        player_id=None,
        registration_type=RegistrationType.TEAM.value,
        status=RegistrationStatus.APPROVED.value,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return registration


def test_create_round_robin_fixtures_saves_matches(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    teams = [
        create_team(db, user.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    matches = create_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[team.id for team in teams],
        fixture_date=date(2099, 1, 2),
        fixture_time=time(10, 0),
    )

    assert len(matches) == 6
    assert all(match.id is not None for match in matches)
    assert all(
        match.tournament_id == tournament.id
        for match in matches
    )
    assert all(
        match.status == "scheduled"
        for match in matches
    )


def test_create_round_robin_fixtures_creates_unique_pairings(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    teams = [
        create_team(db, user.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    matches = create_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[team.id for team in teams],
        fixture_date=date(2099, 1, 3),
        fixture_time=time(12, 0),
    )

    pairings = {
        frozenset(
            (match.team_a_id, match.team_b_id)
        )
        for match in matches
    }

    assert len(pairings) == 6


def test_create_round_robin_fixtures_rejects_unapproved_team(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    approved_team = create_team(db, user.id)
    pending_team = create_team(db, user.id)

    approve_team_registration(
        db,
        tournament.id,
        approved_team.id,
    )

    db.add(
        Registration(
            tournament_id=tournament.id,
            team_id=pending_team.id,
            player_id=None,
            registration_type=RegistrationType.TEAM.value,
            status=RegistrationStatus.PENDING.value,
        )
    )
    db.commit()

    with pytest.raises(BadRequestException):
        create_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[
                approved_team.id,
                pending_team.id,
            ],
            fixture_date=date(2099, 1, 4),
            fixture_time=time(10, 0),
        )

    assert (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament.id
        )
        .count()
        == 0
    )


def test_create_round_robin_fixtures_rejects_missing_tournament(db):
    with pytest.raises(NotFoundException):
        create_round_robin_fixtures(
            db=db,
            tournament_id=999999,
            team_ids=[1, 2],
            fixture_date=date(2099, 1, 5),
            fixture_time=time(10, 0),
        )


def test_create_round_robin_fixtures_rejects_wrong_tournament_format(
    db,
):
    user = create_user(db)

    tournament = create_tournament(
        db,
        user.id,
        tournament_format="single_elimination",
    )

    with pytest.raises(BadRequestException):
        create_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[1, 2],
            fixture_date=date(2099, 1, 6),
            fixture_time=time(10, 0),
        )


def test_create_round_robin_fixtures_prevents_team_schedule_overlap(
    db,
):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    teams = [
        create_team(db, user.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    matches = create_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[team.id for team in teams],
        fixture_date=date(2099, 1, 2),
        fixture_time=time(10, 0),
    )

    teams_by_time = {}

    for match in matches:
        teams_by_time.setdefault(
            match.scheduled_at,
            set(),
        )

        assert (
            match.team_a_id
            not in teams_by_time[match.scheduled_at]
        )
        assert (
            match.team_b_id
            not in teams_by_time[match.scheduled_at]
        )

        teams_by_time[match.scheduled_at].add(
            match.team_a_id
        )
        teams_by_time[match.scheduled_at].add(
            match.team_b_id
        )


def test_create_round_robin_fixtures_rejects_schedule_before_tournament_start(
    db,
):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    teams = [
        create_team(db, user.id)
        for _ in range(2)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    with pytest.raises(
        BadRequestException,
        match="before the tournament",
    ):
        create_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[
                team.id
                for team in teams
            ],
            fixture_date=date(2098, 12, 31),
            fixture_time=time(10, 0),
        )


def test_create_round_robin_fixtures_rejects_schedule_after_tournament_end(
    db,
):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    teams = [
        create_team(db, user.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    with pytest.raises(
        BadRequestException,
        match="exceeds the tournament",
    ):
        create_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[
                team.id
                for team in teams
            ],
            fixture_date=date(2099, 1, 10),
            fixture_time=time(17, 0),
        )


def test_create_round_robin_fixtures_assigns_valid_venue(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)
    venue = create_venue(db)

    teams = [
        create_team(db, user.id)
        for _ in range(2)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    matches = create_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=[
            team.id
            for team in teams
        ],
        fixture_date=date(2099, 1, 7),
        fixture_time=time(10, 0),
        venue_id=venue.id,
    )

    assert len(matches) == 1
    assert matches[0].venue_id == venue.id


def test_create_round_robin_fixtures_rejects_invalid_venue(
    db,
):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    teams = [
        create_team(db, user.id)
        for _ in range(2)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    with pytest.raises(
        NotFoundException,
        match="Venue not found",
    ):
        create_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[
                team.id
                for team in teams
            ],
            fixture_date=date(2099, 1, 7),
            fixture_time=time(11, 0),
            venue_id=999999,
        )


def test_create_round_robin_fixtures_rejects_double_booked_venue(
    db,
):
    user = create_user(db)
    tournament = create_tournament(db, user.id)
    venue = create_venue(db)

    teams = [
        create_team(db, user.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    existing_match = Match(
        tournament_id=tournament.id,
        match_number=1,
        team_a_id=teams[0].id,
        team_b_id=teams[1].id,
        venue_id=venue.id,
        scheduled_at=datetime(
            2099,
            1,
            8,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        status="scheduled",
    )

    db.add(existing_match)
    db.commit()

    with pytest.raises(
        ConflictException,
        match="Venue is already booked",
    ):
        create_round_robin_fixtures(
            db=db,
            tournament_id=tournament.id,
            team_ids=[
                teams[2].id,
                teams[3].id,
            ],
            fixture_date=date(2099, 1, 8),
            fixture_time=time(10, 0),
            venue_id=venue.id,
        )

    assert (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament.id
        )
        .count()
        == 1
    )