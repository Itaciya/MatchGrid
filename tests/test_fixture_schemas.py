from datetime import date, time

import pytest
from pydantic import ValidationError

from app.modules.match.schemas.fixture import (
    FixtureCreate,
    FixtureResponse,
)


def test_valid_fixture_data_is_accepted():
    fixture = FixtureCreate(
        tournament_id=1,
        team_ids=[10, 20],
        venue_id=5,
        fixture_date=date(2026, 10, 10),
        fixture_time=time(10, 0),
    )

    assert fixture.tournament_id == 1
    assert fixture.team_ids == [10, 20]
    assert fixture.venue_id == 5
    assert fixture.fixture_date == date(2026, 10, 10)
    assert fixture.fixture_time == time(10, 0)


def test_invalid_tournament_id_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=0,
            team_ids=[10, 20],
            venue_id=5,
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )


def test_less_than_two_teams_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            team_ids=[10],
            venue_id=5,
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )


def test_duplicate_teams_are_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            team_ids=[10, 10],
            venue_id=5,
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )


def test_invalid_team_id_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            team_ids=[10, 0],
            venue_id=5,
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )


def test_invalid_venue_id_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            team_ids=[10, 20],
            venue_id=0,
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )


def test_missing_venue_id_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            team_ids=[10, 20],
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )


def test_fixture_response_schema_accepts_valid_data():
    fixture = FixtureResponse(
        id=1,
        tournament_id=1,
        match_number=1,
        team_a_id=10,
        team_b_id=20,
        venue_id=5,
        scheduled_at="2026-10-10T10:00:00Z",
        status="scheduled",
        created_at="2026-10-07T10:00:00Z",
        updated_at="2026-10-07T10:00:00Z",
    )

    assert fixture.id == 1
    assert fixture.tournament_id == 1
    assert fixture.match_number == 1
    assert fixture.team_a_id == 10
    assert fixture.team_b_id == 20
    assert fixture.venue_id == 5
    assert fixture.status == "scheduled"