from datetime import date, time

import pytest

from app.modules.match.services.fixture_service import generate_round_robin_fixtures


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


def test_generate_round_robin_fixtures_preserves_schedule():
    fixtures = generate_round_robin_fixtures(
        participant_ids=[1, 2, 3, 4],
        fixture_date=date(2026, 10, 10),
        fixture_time=time(15, 30),
    )

    assert all(
        fixture["scheduled_at"].date() == date(2026, 10, 10)
        for fixture in fixtures
    )

    assert all(
        fixture["scheduled_at"].time() == time(15, 30)
        for fixture in fixtures
    )


def test_generate_round_robin_fixtures_rejects_invalid_participants():
    with pytest.raises(ValueError, match="At least 2 participants"):
        generate_round_robin_fixtures(
            participant_ids=[1],
            fixture_date=date(2026, 10, 10),
            fixture_time=time(10, 0),
        )
