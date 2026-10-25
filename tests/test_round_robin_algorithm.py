from datetime import date, datetime, time, timezone
from itertools import combinations

import pytest

from app.modules.match.services.fixture_service import (
    MATCH_TIME_INTERVAL,
    generate_round_robin_fixtures,
    generate_round_robin_pairings,
    generate_round_robin_rounds,
)

EVEN_COUNTS = [2, 4, 6, 8, 10, 16]
ODD_COUNTS = [3, 5, 7, 9, 15]
ALL_COUNTS = EVEN_COUNTS + ODD_COUNTS
LARGE_COUNTS = [64, 65, 100]

START_DATE = date(2026, 11, 1)
START_TIME = time(9, 0)


def _ids(n, start=1):
    return list(range(start, start + n))


def _expected_pairs(ids):
    return {frozenset(pair) for pair in combinations(ids, 2)}


def _flatten(rounds):
    return [match for current_round in rounds for match in current_round]


# SCRUM-245: even team counts

@pytest.mark.parametrize("n", EVEN_COUNTS)
def test_even_count_has_n_minus_1_rounds_with_half_the_teams_playing(n):
    rounds = generate_round_robin_rounds(_ids(n))

    assert len(rounds) == n - 1
    assert all(len(current_round) == n // 2 for current_round in rounds)


@pytest.mark.parametrize("n", EVEN_COUNTS)
def test_even_count_has_no_byes(n):
    ids = _ids(n)

    for current_round in generate_round_robin_rounds(ids):
        playing = {team for match in current_round for team in match}
        assert playing == set(ids)


def test_four_teams_known_schedule():
    assert generate_round_robin_rounds([1, 2, 3, 4]) == [
        [(1, 4), (2, 3)],
        [(1, 3), (4, 2)],
        [(1, 2), (3, 4)],
    ]


def test_two_teams_play_exactly_one_match():
    assert generate_round_robin_rounds([1, 2]) == [[(1, 2)]]


# SCRUM-245: odd team counts and byes

@pytest.mark.parametrize("n", ODD_COUNTS)
def test_odd_count_has_n_rounds_with_one_team_sitting_out_each_round(n):
    rounds = generate_round_robin_rounds(_ids(n))

    assert len(rounds) == n
    assert all(len(current_round) == (n - 1) // 2 for current_round in rounds)


@pytest.mark.parametrize("n", ODD_COUNTS)
def test_odd_count_every_team_gets_exactly_one_bye(n):
    ids = _ids(n)
    rounds = generate_round_robin_rounds(ids)
    bye_counts = {team: 0 for team in ids}

    for current_round in rounds:
        playing = {team for match in current_round for team in match}
        sitting_out = set(ids) - playing
        assert len(sitting_out) == 1
        for team in sitting_out:
            bye_counts[team] += 1

    assert all(count == 1 for count in bye_counts.values())


@pytest.mark.parametrize("n", ALL_COUNTS)
def test_bye_placeholder_never_appears_in_a_match(n):
    for first, second in _flatten(generate_round_robin_rounds(_ids(n))):
        assert first is not None
        assert second is not None


def test_three_teams_known_schedule():
    assert generate_round_robin_rounds([1, 2, 3]) == [
        [(2, 3)],
        [(1, 3)],
        [(1, 2)],
    ]


# SCRUM-245: every pairing exactly once, no duplicates

@pytest.mark.parametrize("n", ALL_COUNTS)
def test_every_required_pairing_is_generated(n):
    ids = _ids(n)
    generated = {frozenset(pair) for pair in generate_round_robin_pairings(ids)}

    assert generated == _expected_pairs(ids)


@pytest.mark.parametrize("n", ALL_COUNTS)
def test_no_pairing_is_generated_twice(n):
    pairings = generate_round_robin_pairings(_ids(n))

    assert len(pairings) == n * (n - 1) // 2
    assert len({frozenset(pair) for pair in pairings}) == len(pairings)


@pytest.mark.parametrize("n", ALL_COUNTS)
def test_no_team_plays_itself(n):
    for first, second in generate_round_robin_pairings(_ids(n)):
        assert first != second


@pytest.mark.parametrize("n", ALL_COUNTS)
def test_each_team_plays_every_opponent_once(n):
    ids = _ids(n)
    opponents = {team: [] for team in ids}

    for first, second in generate_round_robin_pairings(ids):
        opponents[first].append(second)
        opponents[second].append(first)

    for team, played in opponents.items():
        assert len(played) == n - 1
        assert set(played) == set(ids) - {team}


@pytest.mark.parametrize("n", ALL_COUNTS)
def test_no_team_plays_twice_in_the_same_round(n):
    for current_round in generate_round_robin_rounds(_ids(n)):
        teams = [team for match in current_round for team in match]
        assert len(teams) == len(set(teams))


def test_pairings_are_the_flattened_rounds():
    ids = _ids(7)

    assert generate_round_robin_pairings(ids) == _flatten(
        generate_round_robin_rounds(ids)
    )


def test_team_id_zero_is_treated_as_a_real_team():
    ids = [0, 1, 2, 3]
    generated = {frozenset(pair) for pair in generate_round_robin_pairings(ids)}

    assert generated == _expected_pairs(ids)


def test_non_sequential_ids_are_supported():
    ids = [101, 7, 55, 3, 900]
    generated = {frozenset(pair) for pair in generate_round_robin_pairings(ids)}

    assert generated == _expected_pairs(ids)


# SCRUM-245: invalid input is rejected

@pytest.mark.parametrize("ids", [[], [1]])
def test_fewer_than_two_participants_are_rejected(ids):
    with pytest.raises(ValueError, match="At least 2 participants"):
        generate_round_robin_rounds(ids)


@pytest.mark.parametrize("ids", [[1, 1], [1, 2, 2, 3], [1, 2, 3, 1], [5, 5, 5]])
def test_duplicate_participants_are_rejected(ids):
    with pytest.raises(ValueError, match="Duplicate participants"):
        generate_round_robin_rounds(ids)


@pytest.mark.parametrize("ids", [[], [1], [1, 1]])
def test_pairing_and_fixture_generators_reject_invalid_input(ids):
    with pytest.raises(ValueError):
        generate_round_robin_pairings(ids)

    with pytest.raises(ValueError):
        generate_round_robin_fixtures(ids, START_DATE, START_TIME)


def test_input_list_is_not_modified():
    ids = [4, 2, 9, 1, 7]
    snapshot = list(ids)

    generate_round_robin_rounds(ids)

    assert ids == snapshot


# SCRUM-245: determinism

@pytest.mark.parametrize("n", [4, 7, 16])
def test_same_input_gives_the_same_rounds_every_time(n):
    ids = _ids(n)
    first = generate_round_robin_rounds(ids)

    for _ in range(5):
        assert generate_round_robin_rounds(list(ids)) == first


def test_same_input_gives_the_same_fixtures_every_time():
    ids = _ids(9)
    first = generate_round_robin_fixtures(ids, START_DATE, START_TIME)

    for _ in range(3):
        assert generate_round_robin_fixtures(ids, START_DATE, START_TIME) == first


# SCRUM-245: large inputs

@pytest.mark.parametrize("n", LARGE_COUNTS)
def test_large_tournaments_generate_a_complete_schedule(n):
    ids = _ids(n)
    rounds = generate_round_robin_rounds(ids)
    pairings = _flatten(rounds)

    assert len(rounds) == (n - 1 if n % 2 == 0 else n)
    assert len(pairings) == n * (n - 1) // 2
    assert {frozenset(pair) for pair in pairings} == _expected_pairs(ids)

    for current_round in rounds:
        teams = [team for match in current_round for team in match]
        assert len(teams) == len(set(teams))


# SCRUM-245: fixture generation (times, shape, order)

@pytest.mark.parametrize("n", [2, 3, 8, 11])
def test_fixture_count_matches_the_number_of_pairings(n):
    fixtures = generate_round_robin_fixtures(_ids(n), START_DATE, START_TIME)

    assert len(fixtures) == n * (n - 1) // 2


def test_fixtures_have_the_expected_shape_and_status():
    fixtures = generate_round_robin_fixtures(_ids(6), START_DATE, START_TIME)

    for fixture in fixtures:
        assert set(fixture) == {"team_a_id", "team_b_id", "scheduled_at", "status"}
        assert fixture["status"] == "scheduled"
        assert fixture["team_a_id"] != fixture["team_b_id"]


def test_fixtures_start_at_the_given_time_in_utc():
    fixtures = generate_round_robin_fixtures(_ids(4), START_DATE, START_TIME)

    assert fixtures[0]["scheduled_at"] == datetime(
        2026, 11, 1, 9, 0, tzinfo=timezone.utc
    )
    assert all(f["scheduled_at"].tzinfo is not None for f in fixtures)


def test_fixtures_use_consecutive_one_hour_slots_with_no_overlap():
    fixtures = generate_round_robin_fixtures(_ids(7), START_DATE, START_TIME)
    times = [fixture["scheduled_at"] for fixture in fixtures]

    assert MATCH_TIME_INTERVAL.total_seconds() == 3600
    assert len(times) == len(set(times))

    for earlier, later in zip(times, times[1:]):
        assert later - earlier == MATCH_TIME_INTERVAL


def test_fixtures_follow_the_round_order_of_the_pairings():
    ids = _ids(6)
    fixtures = generate_round_robin_fixtures(ids, START_DATE, START_TIME)

    assert [(f["team_a_id"], f["team_b_id"]) for f in fixtures] == (
        generate_round_robin_pairings(ids)
    )


@pytest.mark.parametrize("n", [5, 6, 64])
def test_fixtures_contain_every_pairing_exactly_once(n):
    ids = _ids(n)
    fixtures = generate_round_robin_fixtures(ids, START_DATE, START_TIME)
    pairs = [frozenset((f["team_a_id"], f["team_b_id"])) for f in fixtures]

    assert len(pairs) == len(set(pairs))
    assert set(pairs) == _expected_pairs(ids)