import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.match.services.match_validation import (
    validate_team_for_fixture,
    validate_teams_for_fixture,
)
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import (
    RegistrationStatus,
    RegistrationType,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def create_user(db, role="captain"):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash="test_password_hash",
        role=role,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"Fixture Validation Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 2, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    return tournament


def create_team(db, captain_id):
    team = Team(
        name=f"Fixture Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )

    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def create_team_registration(
    db,
    tournament_id,
    team_id,
    status,
):
    registration = Registration(
        tournament_id=tournament_id,
        team_id=team_id,
        player_id=None,
        registration_type=RegistrationType.TEAM.value,
        status=status.value,
    )

    db.add(registration)
    db.commit()
    db.refresh(registration)

    return registration


def test_validate_team_for_fixture_allows_approved_team(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)
    team = create_team(db, user.id)

    create_team_registration(
        db,
        tournament.id,
        team.id,
        RegistrationStatus.APPROVED,
    )

    result = validate_team_for_fixture(
        db,
        tournament.id,
        team.id,
    )

    assert result.id == team.id


@pytest.mark.parametrize(
    "registration_status",
    [
        RegistrationStatus.PENDING,
        RegistrationStatus.REJECTED,
        RegistrationStatus.CANCELLED,
    ],
)
def test_validate_team_for_fixture_rejects_unapproved_team(
    db,
    registration_status,
):
    user = create_user(db)
    tournament = create_tournament(db, user.id)
    team = create_team(db, user.id)

    create_team_registration(
        db,
        tournament.id,
        team.id,
        registration_status,
    )

    with pytest.raises(BadRequestException):
        validate_team_for_fixture(
            db,
            tournament.id,
            team.id,
        )


def test_validate_team_for_fixture_rejects_unregistered_team(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)
    team = create_team(db, user.id)

    with pytest.raises(BadRequestException):
        validate_team_for_fixture(
            db,
            tournament.id,
            team.id,
        )


def test_validate_team_for_fixture_rejects_nonexistent_team(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    with pytest.raises(NotFoundException):
        validate_team_for_fixture(
            db,
            tournament.id,
            999999,
        )


def test_validate_teams_for_fixture_allows_approved_teams(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    team_one = create_team(db, user.id)
    team_two = create_team(db, user.id)

    create_team_registration(
        db,
        tournament.id,
        team_one.id,
        RegistrationStatus.APPROVED,
    )

    create_team_registration(
        db,
        tournament.id,
        team_two.id,
        RegistrationStatus.APPROVED,
    )

    result = validate_teams_for_fixture(
        db,
        tournament.id,
        [team_one.id, team_two.id],
    )

    assert len(result) == 2
    assert result[0].id == team_one.id
    assert result[1].id == team_two.id


def test_validate_teams_for_fixture_rejects_empty_team_list(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    with pytest.raises(BadRequestException):
        validate_teams_for_fixture(
            db,
            tournament.id,
            [],
        )


def test_validate_teams_for_fixture_rejects_unapproved_team(db):
    user = create_user(db)
    tournament = create_tournament(db, user.id)

    approved_team = create_team(db, user.id)
    pending_team = create_team(db, user.id)

    create_team_registration(
        db,
        tournament.id,
        approved_team.id,
        RegistrationStatus.APPROVED,
    )

    create_team_registration(
        db,
        tournament.id,
        pending_team.id,
        RegistrationStatus.PENDING,
    )

    with pytest.raises(BadRequestException):
        validate_teams_for_fixture(
            db,
            tournament.id,
            [approved_team.id, pending_team.id],
        )