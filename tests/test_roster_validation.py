import pytest

from app.core.exceptions import ConflictException
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.player_team.services.player_service import (
    validate_player_for_roster,
)


def _make_player(
    status=PlayerStatus.ACTIVE,
    team_id=None,
):
    return Player(
        user_id=1,
        team_id=team_id,
        first_name="John",
        last_name="Doe",
        status=status,
    )


def test_active_player_without_team_is_eligible():
    player = _make_player(
        status=PlayerStatus.ACTIVE,
        team_id=None,
    )

    validate_player_for_roster(player)


def test_inactive_player_is_rejected():
    player = _make_player(
        status=PlayerStatus.INACTIVE,
        team_id=None,
    )

    with pytest.raises(ConflictException) as exc_info:
        validate_player_for_roster(player)

    assert exc_info.value.detail == (
        "Only active players can be added to a team"
    )


def test_suspended_player_is_rejected():
    player = _make_player(
        status=PlayerStatus.SUSPENDED,
        team_id=None,
    )

    with pytest.raises(ConflictException) as exc_info:
        validate_player_for_roster(player)

    assert exc_info.value.detail == (
        "Only active players can be added to a team"
    )


def test_player_already_in_team_is_rejected():
    player = _make_player(
        status=PlayerStatus.ACTIVE,
        team_id=10,
    )

    with pytest.raises(ConflictException) as exc_info:
        validate_player_for_roster(player)

    assert exc_info.value.detail == (
        "Player already belongs to a team"
    )