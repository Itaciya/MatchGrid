import pytest
from pydantic import ValidationError

from app.modules.player_team.schemas.team import (
    TeamCreate,
    TeamResponse,
    TeamUpdate,
)


def test_team_create_accepts_valid_data():
    team = TeamCreate(
        name="Test Team",
        captain_id=1,
    )

    assert team.name == "Test Team"
    assert team.captain_id == 1


def test_team_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        TeamCreate(
            name="",
            captain_id=1,
        )


def test_team_create_rejects_invalid_captain_id():
    with pytest.raises(ValidationError):
        TeamCreate(
            name="Test Team",
            captain_id=0,
        )


def test_team_create_rejects_negative_captain_id():
    with pytest.raises(ValidationError):
        TeamCreate(
            name="Test Team",
            captain_id=-1,
        )


def test_team_create_rejects_name_longer_than_100_characters():
    with pytest.raises(ValidationError):
        TeamCreate(
            name="A" * 101,
            captain_id=1,
        )


def test_team_update_accepts_valid_data():
    team = TeamUpdate(
        name="Updated Team",
        captain_id=2,
        status="active",
    )

    assert team.name == "Updated Team"
    assert team.captain_id == 2
    assert team.status.value == "active"


def test_team_update_allows_partial_update():
    team = TeamUpdate(
        name="Updated Team",
    )

    assert team.name == "Updated Team"
    assert team.captain_id is None
    assert team.status is None


def test_team_update_rejects_invalid_status():
    with pytest.raises(ValidationError):
        TeamUpdate(
            name="Updated Team",
            status="invalid_status",
        )


def test_team_update_rejects_invalid_captain_id():
    with pytest.raises(ValidationError):
        TeamUpdate(
            captain_id=0,
        )


def test_team_response_contains_required_information():
    data = {
        "id": 1,
        "name": "Test Team",
        "captain_id": 10,
        "status": "active",
        "created_at": "2026-10-02T10:00:00Z",
        "updated_at": "2026-10-02T10:00:00Z",
        "players": [],
    }

    team = TeamResponse.model_validate(data)

    assert team.id == 1
    assert team.name == "Test Team"
    assert team.captain_id == 10
    assert team.status.value == "active"
    assert team.players == []


def test_team_response_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        TeamResponse(
            id=1,
            name="Test Team",
        )