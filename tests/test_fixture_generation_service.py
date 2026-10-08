from datetime import date, time, timezone

import pytest

from app.modules.match.services.fixture_service import (
    generate_round_robin_fixtures,
)


def test_generate_round_robin_fixtures_returns_expected_matches():
    fixtures = generate_round_robin_fixtures(
        participant_ids=[1, 2, 3, 4],
        fixture_date=date(2026, 10, 10),
        fixture_time=time(10, 0),
    )

    assert len(fixtures) == 6

    pairings = {
        frozenset((fixture["team_a_id"], fixture["team_b_id"]))
        for fixture in fixtures
    }

    assert len(pairings) == 6


def test_generate_round_robin_fixtures_assigns_separate_round_times():
    fixtures = generate_round_robin_fixtures(
        participant_ids=[1, 2, 3, 4],
        fixture_date=date(2026, 10, 10),
        fixture_time=time(10, 0),
    )

    scheduled_times = {
        fixture["scheduled_at"]
        for fixture in fixtures
    }

    assert len(scheduled_times) == 3

    assert all(
        fixture["scheduled_at"].date() == date(2026, 10, 10)
        for fixture in fixtures
    )

    assert sorted(
        fixture["scheduled_at"].time()
        for fixture in fixtures
    ) == [
        time(10, 0),
        time(10, 0),
        time(11, 0),
        time(11, 0),
        time(12, 0),
        time(12, 0),
    ]


def test_generate_round_robin_fixtures_uses_utc_timezone():
    fixtures = generate_round_robin_fixtures(
        participant_ids=[1, 2, 3, 4],
        fixture_date=date(2026, 10, 10),
        fixture_time=time(15, 30),
    )

    assert all(
        fixture["scheduled_at"].tzinfo == timezone.utc
        for fixture in fixtures
    )


def test_generate_round_robin_fixtures_prevents_team_overlap():
    fixtures = generate_round_robin_fixtures(
        participant_ids=[1, 2, 3, 4],
        fixture_date=date(2026, 10, 10),
        fixture_time=time(10, 0),
    )

    teams_by_time = {}

    for fixture in fixtures:
        scheduled_at = fixture["scheduled_at"]
        teams_by_time.setdefault(scheduled_at, set())

        assert fixture["team_a_id"] not in teams_by_time[scheduled_at]
        assert fixture["team_b_id"] not in teams_by_time[scheduled_at]

        teams_by_time[scheduled_at].add(fixture["team_a_id"])
        teams_by_time[scheduled_at].add(fixture["team_b_id"])


def test_generate_round_robin_fixtures_rejects_duplicate_participants():
    with pytest.raises(
        ValueError,
        match="Duplicate participants are not allowed",
    ):
        generate_round_robin_fixtures(
            participant_ids=[1, 2, 2, 3],
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )


def test_generate_round_robin_fixtures_rejects_invalid_participants():
    with pytest.raises(ValueError, match="At least 2 participants"):
        generate_round_robin_fixtures(
            participant_ids=[1],
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )