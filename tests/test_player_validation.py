import pytest
from pydantic import ValidationError

from app.modules.player_team.schemas.player import (
    PlayerCreate,
    PlayerUpdate,
)


def test_player_create_accepts_valid_information():
    data = PlayerCreate(
        team_id=1,
        first_name="John",
        last_name="Doe",
    )

    assert data.team_id == 1
    assert data.first_name == "John"
    assert data.last_name == "Doe"


def test_player_create_strips_name_whitespace():
    data = PlayerCreate(
        team_id=1,
        first_name="  John  ",
        last_name="  Doe  ",
    )

    assert data.first_name == "John"
    assert data.last_name == "Doe"


def test_player_create_rejects_invalid_team_id():
    with pytest.raises(ValidationError):
        PlayerCreate(
            team_id=0,
            first_name="John",
            last_name="Doe",
        )


def test_player_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        PlayerCreate(
            team_id=1,
            first_name="   ",
            last_name="Doe",
        )


def test_player_create_rejects_invalid_name_format():
    with pytest.raises(ValidationError):
        PlayerCreate(
            team_id=1,
            first_name="John123",
            last_name="Doe",
        )


def test_player_update_accepts_valid_information():
    data = PlayerUpdate(
        first_name="Jane",
        last_name="Smith",
        team_id=2,
    )

    assert data.first_name == "Jane"
    assert data.last_name == "Smith"
    assert data.team_id == 2


def test_player_update_allows_partial_update():
    data = PlayerUpdate(first_name="Jane")

    assert data.first_name == "Jane"
    assert data.last_name is None
    assert data.team_id is None


def test_player_update_rejects_invalid_name():
    with pytest.raises(ValidationError):
        PlayerUpdate(first_name="Jane123")


def test_player_update_rejects_invalid_team_id():
    with pytest.raises(ValidationError):
        PlayerUpdate(team_id=0)