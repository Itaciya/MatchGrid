from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.core.security import hash_password
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.registration.schemas.registration import (
    RegistrationCreate,
    RegistrationType,
)
from app.modules.registration.services.registration_service import (
    create_team_registration,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def _make_user(db):
    user = User(
        email=f"registration_roster_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role="player",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_team(db, captain):
    team = Team(
        name=f"Registration Roster Team {uuid4()}",
        captain_id=captain.id,
        status="active",
    )
    db.add(team)
    db.flush()
    return team


def _make_player(db, team, status="active"):
    user = _make_user(db)

    player = Player(
        user_id=user.id,
        team_id=team.id,
        first_name="Registration",
        last_name="Player",
        status=status,
    )
    db.add(player)
    db.flush()
    return player


def _make_tournament(db, organizer):
    now = datetime.now(timezone.utc)

    tournament = Tournament(
        name=f"Registration Roster Tournament {uuid4()}",
        description="Registration roster validation test",
        format="league",
        start_date=now + timedelta(days=10),
        end_date=now + timedelta(days=20),
        status="upcoming",
        organizer_id=organizer.id,
    )
    db.add(tournament)
    db.flush()
    return tournament


def _make_registration(tournament, team):
    return RegistrationCreate(
        tournament_id=tournament.id,
        team_id=team.id,
        registration_type=RegistrationType.TEAM,
    )


def test_valid_team_roster_can_register(db):
    captain = _make_user(db)
    team = _make_team(db, captain)

    _make_player(db, team, status="active")
    _make_player(db, team, status="active")

    tournament = _make_tournament(db, captain)

    registration = create_team_registration(
        db,
        captain.id,
        _make_registration(tournament, team),
    )

    assert registration.id is not None
    assert registration.team_id == team.id
    assert registration.tournament_id == tournament.id


def test_inactive_player_prevents_team_registration(db):
    captain = _make_user(db)
    team = _make_team(db, captain)

    _make_player(db, team, status="inactive")

    tournament = _make_tournament(db, captain)

    with pytest.raises(ConflictException) as exc_info:
        create_team_registration(
            db,
            captain.id,
            _make_registration(tournament, team),
        )

    assert exc_info.value.detail == (
        "Only active players can be added to a team"
    )


def test_suspended_player_prevents_team_registration(db):
    captain = _make_user(db)
    team = _make_team(db, captain)

    _make_player(db, team, status="suspended")

    tournament = _make_tournament(db, captain)

    with pytest.raises(ConflictException) as exc_info:
        create_team_registration(
            db,
            captain.id,
            _make_registration(tournament, team),
        )

    assert exc_info.value.detail == (
        "Only active players can be added to a team"
    )


def test_empty_team_roster_is_allowed_without_minimum_size(db):
    captain = _make_user(db)
    team = _make_team(db, captain)

    tournament = _make_tournament(db, captain)

    registration = create_team_registration(
        db,
        captain.id,
        _make_registration(tournament, team),
    )

    assert registration.id is not None
    assert registration.team_id == team.id