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
        participant_ids=[10, 20],
        format="round_robin",
        fixture_date=date(2026, 10, 10),
        fixture_time=time(10, 0),
        venue="Main Stadium",
    )

    assert fixture.tournament_id == 1
    assert fixture.participant_ids == [10, 20]
    assert fixture.format == "round_robin"
    assert fixture.venue == "Main Stadium"


def test_invalid_tournament_id_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=0,
            participant_ids=[10, 20],
            format="round_robin",
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
            venue="Main Stadium",
        )


def test_less_than_two_participants_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            participant_ids=[10],
            format="round_robin",
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
            venue="Main Stadium",
        )


def test_duplicate_participants_are_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            participant_ids=[10, 10],
            format="round_robin",
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
            venue="Main Stadium",
        )


def test_invalid_participant_id_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            participant_ids=[10, 0],
            format="round_robin",
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
            venue="Main Stadium",
        )


def test_empty_format_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            participant_ids=[10, 20],
            format="",
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
            venue="Main Stadium",
        )


def test_empty_venue_is_rejected():
    with pytest.raises(ValidationError):
        FixtureCreate(
            tournament_id=1,
            participant_ids=[10, 20],
            format="round_robin",
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
            venue="",
        )


def test_fixture_response_schema_accepts_valid_data():
    fixture = FixtureResponse(
        id=1,
        tournament_id=1,
        participant_ids=[10, 20],
        format="round_robin",
        fixture_date=date(2026, 10, 10),
        fixture_time=time(10, 0),
        venue="Main Stadium",
        status="scheduled",
        created_at="2026-10-07T10:00:00Z",
        updated_at="2026-10-07T10:00:00Z",
    )

    assert fixture.id == 1
    assert fixture.status == "scheduled"
