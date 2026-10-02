from uuid import uuid4

import pytest

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.core.security import hash_password
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.player_team.services.player_service import validate_team_roster
from app.modules.user.models import User


def _make_user(db):
    user = User(
        email=f"roster_validation_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role="player",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _make_player(db, status="active", team_id=None):
    user = _make_user(db)

    player = Player(
        user_id=user.id,
        team_id=team_id,
        first_name="John",
        last_name="Doe",
        status=status,
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    return player


def test_valid_roster_is_accepted(db):
    player_one = _make_player(db)
    player_two = _make_player(db)

    players = validate_team_roster(
        db,
        [player_one.id, player_two.id],
        min_size=2,
        max_size=5,
    )

    assert len(players) == 2
    assert {player.id for player in players} == {
        player_one.id,
        player_two.id,
    }


def test_roster_below_minimum_size_is_rejected(db):
    player = _make_player(db)

    with pytest.raises(BadRequestException) as exc_info:
        validate_team_roster(
            db,
            [player.id],
            min_size=2,
            max_size=5,
        )

    assert exc_info.value.detail == (
        "Roster must contain at least 2 players"
    )


def test_roster_above_maximum_size_is_rejected(db):
    players = [_make_player(db) for _ in range(3)]

    with pytest.raises(BadRequestException) as exc_info:
        validate_team_roster(
            db,
            [player.id for player in players],
            min_size=1,
            max_size=2,
        )

    assert exc_info.value.detail == (
        "Roster cannot contain more than 2 players"
    )


def test_duplicate_players_are_rejected(db):
    player = _make_player(db)

    with pytest.raises(BadRequestException) as exc_info:
        validate_team_roster(
            db,
            [player.id, player.id],
            min_size=1,
            max_size=5,
        )

    assert exc_info.value.detail == (
        "Duplicate players are not allowed in a roster"
    )


def test_missing_player_is_rejected(db):
    player = _make_player(db)

    with pytest.raises(NotFoundException) as exc_info:
        validate_team_roster(
            db,
            [player.id, 999999],
            min_size=1,
            max_size=5,
        )

    assert exc_info.value.detail == (
        "One or more players were not found"
    )


def test_inactive_player_is_rejected(db):
    player = _make_player(db, status="inactive")

    with pytest.raises(ConflictException) as exc_info:
        validate_team_roster(
            db,
            [player.id],
            min_size=1,
            max_size=5,
        )

    assert exc_info.value.detail == (
        "Only active players can be added to a team"
    )


def test_suspended_player_is_rejected(db):
    player = _make_player(db, status="suspended")

    with pytest.raises(ConflictException) as exc_info:
        validate_team_roster(
            db,
            [player.id],
            min_size=1,
            max_size=5,
        )

    assert exc_info.value.detail == (
        "Only active players can be added to a team"
    )


def test_player_already_in_team_is_rejected(db):
    captain = _make_user(db)

    team = Team(
        name=f"Roster Validation Team {uuid4()}",
        captain_id=captain.id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    player = _make_player(db, team_id=team.id)

    with pytest.raises(ConflictException) as exc_info:
        validate_team_roster(
            db,
            [player.id],
            min_size=1,
            max_size=5,
        )

    assert exc_info.value.detail == (
        "Player already belongs to a team"
    )

def test_players_already_in_same_team_are_accepted(db):
    captain = _make_user(db)

    team = Team(
        name=f"Same Team Validation {uuid4()}",
        captain_id=captain.id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    player_one = _make_player(db, team_id=team.id)
    player_two = _make_player(db, team_id=team.id)

    players = validate_team_roster(
        db,
        [player_one.id, player_two.id],
        min_size=2,
        max_size=5,
        team_id=team.id,
    )

    assert len(players) == 2
    assert {player.id for player in players} == {
        player_one.id,
        player_two.id,
    }


def test_player_from_different_team_is_rejected(db):
    captain_one = _make_user(db)
    captain_two = _make_user(db)

    team_one = Team(
        name=f"Validation Team One {uuid4()}",
        captain_id=captain_one.id,
        status="active",
    )
    team_two = Team(
        name=f"Validation Team Two {uuid4()}",
        captain_id=captain_two.id,
        status="active",
    )

    db.add_all([team_one, team_two])
    db.commit()
    db.refresh(team_one)
    db.refresh(team_two)

    player = _make_player(db, team_id=team_one.id)

    with pytest.raises(ConflictException) as exc_info:
        validate_team_roster(
            db,
            [player.id],
            min_size=1,
            max_size=5,
            team_id=team_two.id,
        )

    assert exc_info.value.detail == (
        "Player does not belong to this team"
    )