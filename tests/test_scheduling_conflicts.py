import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.modules.match.services.scheduling_conflict_service import (
    MATCH_DURATION,
    check_player_conflicts,
    check_team_conflicts,
    check_time_slot_conflicts,
    check_venue_conflicts,
    has_time_overlap,
    validate_schedule_conflicts,
)

BASE = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def _team(player_ids):
    return SimpleNamespace(players=[SimpleNamespace(id=p) for p in player_ids])


def _match(id, a=None, b=None, venue=None, start=BASE, players_a=(), players_b=()):
    return SimpleNamespace(
        id=id,
        team_a_id=a,
        team_b_id=b,
        venue_id=venue,
        scheduled_at=start,
        team_a=_team(players_a) if players_a else None,
        team_b=_team(players_b) if players_b else None,
    )


def _keys(conflicts):
    return {(c["type"], frozenset(c["match_ids"])) for c in conflicts}


# SCRUM-248: overlapping times and boundaries

@pytest.mark.parametrize(
    "offset,expected",
    [
        (timedelta(0), True),
        (timedelta(minutes=30), True),
        (timedelta(minutes=59, seconds=59), True),
        (timedelta(minutes=59, seconds=59, microseconds=999999), True),
        (HOUR, False),
        (HOUR + timedelta(seconds=1), False),
        (timedelta(hours=2), False),
        (-timedelta(minutes=30), True),
        (-timedelta(minutes=59, seconds=59), True),
        (-HOUR, False),
        (-timedelta(hours=3), False),
    ],
)
def test_time_overlap_boundaries(offset, expected):
    assert has_time_overlap(BASE, BASE + offset) is expected
    assert has_time_overlap(BASE + offset, BASE) is expected


def test_match_duration_is_one_hour():
    assert MATCH_DURATION == HOUR


# SCRUM-248: team conflicts

def test_same_team_in_overlapping_matches_is_a_conflict():
    conflicts = check_team_conflicts(
        [_match(1, a=1, b=2), _match(2, a=1, b=3, start=BASE + timedelta(minutes=30))]
    )

    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "team_conflict"
    assert conflicts[0]["team_ids"] == [1]
    assert conflicts[0]["match_ids"] == [1, 2]


def test_team_in_different_slots_of_two_matches_still_conflicts():
    conflicts = check_team_conflicts([_match(1, a=1, b=2), _match(2, a=3, b=1)])

    assert len(conflicts) == 1
    assert conflicts[0]["team_ids"] == [1]


def test_same_team_back_to_back_is_not_a_conflict():
    assert check_team_conflicts([_match(1, a=1, b=2), _match(2, a=1, b=3, start=BASE + HOUR)]) == []


def test_same_team_one_second_before_the_end_is_a_conflict():
    later = BASE + HOUR - timedelta(seconds=1)

    assert len(check_team_conflicts([_match(1, a=1, b=2), _match(2, a=1, b=3, start=later)])) == 1


def test_different_teams_at_the_same_time_are_not_a_conflict():
    assert check_team_conflicts([_match(1, a=1, b=2), _match(2, a=3, b=4)]) == []


def test_rematch_at_the_same_time_reports_both_teams_once():
    conflicts = check_team_conflicts([_match(1, a=1, b=2), _match(2, a=2, b=1)])

    assert len(conflicts) == 1
    assert set(conflicts[0]["team_ids"]) == {1, 2}


def test_missing_teams_are_never_treated_as_a_shared_team():
    assert check_team_conflicts([_match(1, a=1, b=None), _match(2, a=2, b=None)]) == []


def test_three_overlapping_matches_for_one_team_give_three_conflicts():
    matches = [_match(1, a=1, b=2), _match(2, a=1, b=3), _match(3, a=1, b=4)]

    assert _keys(check_team_conflicts(matches)) == {
        ("team_conflict", frozenset({1, 2})),
        ("team_conflict", frozenset({1, 3})),
        ("team_conflict", frozenset({2, 3})),
    }


def test_no_matches_give_no_team_conflicts():
    assert check_team_conflicts([]) == []
    assert check_team_conflicts([_match(1, a=1, b=2)]) == []


# SCRUM-248: venue conflicts

def test_same_venue_overlapping_is_a_conflict():
    conflicts = check_venue_conflicts(
        [_match(1, a=1, b=2, venue=5), _match(2, a=3, b=4, venue=5, start=BASE + timedelta(minutes=15))]
    )

    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "venue_conflict"
    assert conflicts[0]["venue_id"] == 5
    assert conflicts[0]["match_ids"] == [1, 2]


def test_same_venue_back_to_back_is_not_a_conflict():
    assert check_venue_conflicts(
        [_match(1, a=1, b=2, venue=5), _match(2, a=3, b=4, venue=5, start=BASE + HOUR)]
    ) == []


def test_different_venues_at_the_same_time_are_not_a_conflict():
    assert check_venue_conflicts(
        [_match(1, a=1, b=2, venue=5), _match(2, a=3, b=4, venue=6)]
    ) == []


def test_matches_without_a_venue_never_conflict_on_venue():
    assert check_venue_conflicts([_match(1, a=1, b=2), _match(2, a=3, b=4)]) == []
    assert check_venue_conflicts(
        [_match(1, a=1, b=2, venue=5), _match(2, a=3, b=4)]
    ) == []


def test_time_slot_conflict_needs_the_same_venue_and_overlap():
    overlapping = [_match(1, venue=5), _match(2, venue=5)]
    other_venue = [_match(1, venue=5), _match(2, venue=6)]
    no_venue = [_match(1), _match(2)]
    back_to_back = [_match(1, venue=5), _match(2, venue=5, start=BASE + HOUR)]

    conflicts = check_time_slot_conflicts(overlapping)
    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "time_slot_conflict"
    assert check_time_slot_conflicts(other_venue) == []
    assert check_time_slot_conflicts(no_venue) == []
    assert check_time_slot_conflicts(back_to_back) == []


# SCRUM-248: player conflicts

def test_player_in_two_teams_playing_at_once_is_a_conflict():
    conflicts = check_player_conflicts(
        [
            _match(1, a=1, b=2, players_a=[7, 8], players_b=[9]),
            _match(2, a=3, b=4, players_a=[7], players_b=[10]),
        ]
    )

    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "player_conflict"
    assert conflicts[0]["player_ids"] == [7]
    assert conflicts[0]["match_ids"] == [1, 2]


def test_different_players_are_not_a_conflict():
    assert check_player_conflicts(
        [_match(1, a=1, b=2, players_a=[1], players_b=[2]), _match(2, a=3, b=4, players_a=[3], players_b=[4])]
    ) == []


def test_shared_player_at_different_times_is_not_a_conflict():
    assert check_player_conflicts(
        [
            _match(1, a=1, b=2, players_a=[7]),
            _match(2, a=3, b=4, players_a=[7], start=BASE + HOUR),
        ]
    ) == []


def test_matches_without_teams_have_no_player_conflicts():
    assert check_player_conflicts([_match(1), _match(2)]) == []


# SCRUM-248: validate_schedule_conflicts

def test_valid_schedule_has_no_conflicts():
    candidates = [
        _match(1, a=1, b=2, venue=5, start=BASE),
        _match(2, a=3, b=4, venue=5, start=BASE + HOUR),
        _match(3, a=1, b=3, venue=5, start=BASE + 2 * HOUR),
        _match(4, a=2, b=4, venue=6, start=BASE + 2 * HOUR),
    ]

    assert validate_schedule_conflicts(candidates) == []


def test_parallel_matches_with_different_teams_and_venues_are_valid():
    assert validate_schedule_conflicts(
        [_match(1, a=1, b=2, venue=5), _match(2, a=3, b=4, venue=6)]
    ) == []


def test_empty_candidates_give_no_conflicts():
    assert validate_schedule_conflicts([]) == []
    assert validate_schedule_conflicts([], existing_matches=[_match(1, a=1, b=2)]) == []


def test_conflict_among_candidates_is_detected():
    conflicts = validate_schedule_conflicts([_match(1, a=1, b=2), _match(2, a=1, b=3)])

    assert _keys(conflicts) == {("team_conflict", frozenset({1, 2}))}


def test_candidate_conflicting_with_an_existing_match_is_detected():
    conflicts = validate_schedule_conflicts(
        [_match(10, a=1, b=2)], existing_matches=[_match(1, a=1, b=3)]
    )

    assert _keys(conflicts) == {("team_conflict", frozenset({1, 10}))}
    assert conflicts[0]["match_ids"] == [1, 10]


def test_venue_conflict_with_an_existing_match_is_detected():
    conflicts = validate_schedule_conflicts(
        [_match(10, a=1, b=2, venue=5)], existing_matches=[_match(1, a=3, b=4, venue=5)]
    )

    assert _keys(conflicts) == {("venue_conflict", frozenset({1, 10}))}


def test_candidate_at_the_boundary_of_an_existing_match_is_valid():
    assert validate_schedule_conflicts(
        [_match(10, a=1, b=2, venue=5, start=BASE + HOUR)],
        existing_matches=[_match(1, a=1, b=2, venue=5)],
    ) == []


def test_existing_matches_conflicting_with_each_other_are_not_reported():
    assert validate_schedule_conflicts(
        [_match(10, a=8, b=9, venue=7, start=BASE + 5 * HOUR)],
        existing_matches=[_match(1, a=1, b=2), _match(2, a=1, b=3)],
    ) == []


def test_multiple_conflict_types_are_all_reported():
    candidates = [
        _match(1, a=1, b=2, venue=5, players_a=[7]),
        _match(2, a=1, b=3, venue=5),
        _match(3, a=4, b=5, venue=6, players_a=[7]),
        _match(4, a=6, b=6 + 1, venue=5, start=BASE + timedelta(minutes=10)),
    ]

    types = {c["type"] for c in validate_schedule_conflicts(candidates)}

    assert types == {"team_conflict", "venue_conflict", "player_conflict"}


def test_one_pair_with_a_team_and_venue_clash_reports_both_types():
    conflicts = validate_schedule_conflicts(
        [_match(1, a=1, b=2, venue=5), _match(2, a=1, b=3, venue=5)]
    )

    assert _keys(conflicts) == {
        ("team_conflict", frozenset({1, 2})),
        ("venue_conflict", frozenset({1, 2})),
    }


def test_excluded_match_ids_are_ignored_on_both_sides():
    candidates = [_match(10, a=1, b=2)]
    existing = [_match(1, a=1, b=3)]

    assert validate_schedule_conflicts(candidates, existing, exclude_match_ids={1}) == []
    assert validate_schedule_conflicts(candidates, existing, exclude_match_ids={10}) == []
    assert len(validate_schedule_conflicts(candidates, existing, exclude_match_ids={99})) == 1


def test_candidate_replacing_an_existing_match_does_not_conflict_with_itself():
    assert validate_schedule_conflicts(
        [_match(1, a=1, b=2, venue=5)], existing_matches=[_match(1, a=1, b=2, venue=5)]
    ) == []


def test_result_does_not_depend_on_candidate_order():
    candidates = [
        _match(1, a=1, b=2, venue=5),
        _match(2, a=1, b=3, venue=6),
        _match(3, a=4, b=5, venue=5),
    ]

    forward = _keys(validate_schedule_conflicts(candidates))
    backward = _keys(validate_schedule_conflicts(list(reversed(candidates))))

    assert forward == backward
    assert len(forward) == 2


def test_same_input_gives_the_same_result_every_time():
    candidates = [_match(1, a=1, b=2, venue=5), _match(2, a=1, b=3, venue=5)]
    first = validate_schedule_conflicts(candidates)

    for _ in range(5):
        assert validate_schedule_conflicts(candidates) == first


def test_inputs_are_not_modified():
    candidates = [_match(1, a=1, b=2), _match(2, a=1, b=3)]
    existing = [_match(3, a=1, b=4)]

    validate_schedule_conflicts(candidates, existing, exclude_match_ids={99})

    assert [m.id for m in candidates] == [1, 2]
    assert [m.id for m in existing] == [3]


def test_a_full_round_robin_style_schedule_is_conflict_free():
    # 8 teams, one match per slot, one venue, every team plays once per round.
    rounds = [
        [(1, 8), (2, 7), (3, 6), (4, 5)],
        [(1, 7), (8, 6), (2, 5), (3, 4)],
        [(1, 6), (7, 5), (8, 4), (2, 3)],
    ]
    candidates = []
    slot = 0
    for pairings in rounds:
        for a, b in pairings:
            candidates.append(_match(len(candidates) + 1, a=a, b=b, venue=1, start=BASE + slot * HOUR))
            slot += 1

    assert validate_schedule_conflicts(candidates) == []


def test_large_schedule_is_checked_quickly():
    candidates = [
        _match(i, a=2 * i, b=2 * i + 1, venue=1, start=BASE + i * HOUR)
        for i in range(1, 151)
    ]
    existing = [
        _match(1000 + i, a=5000 + 2 * i, b=5001 + 2 * i, venue=2, start=BASE + i * HOUR)
        for i in range(150)
    ]

    started = time.perf_counter()
    conflicts = validate_schedule_conflicts(candidates, existing)
    elapsed = time.perf_counter() - started

    assert conflicts == []
    assert elapsed < 5.0


def test_large_schedule_with_one_clash_reports_exactly_one_conflict():
    candidates = [
        _match(i, a=2 * i, b=2 * i + 1, venue=1, start=BASE + i * HOUR)
        for i in range(1, 101)
    ]
    candidates.append(_match(999, a=2, b=4000, venue=3, start=BASE + 1 * HOUR))

    conflicts = validate_schedule_conflicts(candidates)

    assert _keys(conflicts) == {("team_conflict", frozenset({1, 999}))}


def test_every_conflict_between_unsaved_candidates_is_reported():
    # create_round_robin_fixtures validates unsaved matches, which all have id None.
    candidates = [_match(None, a=1, b=2), _match(None, a=1, b=3), _match(None, a=1, b=4)]

    assert len(validate_schedule_conflicts(candidates)) == 3