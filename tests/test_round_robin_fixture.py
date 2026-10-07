from app.modules.match.services.fixture_service import (
    generate_round_robin_pairings,
    generate_round_robin_rounds,
)


def test_four_participants_generate_all_pairings():
    rounds = generate_round_robin_rounds([1, 2, 3, 4])

    assert len(rounds) == 3
    assert all(len(current_round) == 2 for current_round in rounds)

    pairings = {
        frozenset(match)
        for current_round in rounds
        for match in current_round
    }

    expected = {
        frozenset((1, 2)),
        frozenset((1, 3)),
        frozenset((1, 4)),
        frozenset((2, 3)),
        frozenset((2, 4)),
        frozenset((3, 4)),
    }

    assert pairings == expected


def test_no_participant_plays_twice_in_same_round():
    rounds = generate_round_robin_rounds([1, 2, 3, 4, 5, 6])

    for current_round in rounds:
        participants = [
            participant
            for match in current_round
            for participant in match
        ]

        assert len(participants) == len(set(participants))


def test_odd_participants_are_handled_with_bye():
    rounds = generate_round_robin_rounds([1, 2, 3, 4, 5])

    assert len(rounds) == 5
    assert all(len(current_round) == 2 for current_round in rounds)

    pairings = generate_round_robin_pairings([1, 2, 3, 4, 5])

    assert len(pairings) == 10
    assert len({frozenset(match) for match in pairings}) == 10


def test_duplicate_participants_are_rejected():
    try:
        generate_round_robin_rounds([1, 2, 2, 3])
        assert False
    except ValueError as exc:
        assert str(exc) == "Duplicate participants are not allowed"


def test_less_than_two_participants_are_rejected():
    try:
        generate_round_robin_rounds([1])
        assert False
    except ValueError as exc:
        assert str(exc) == "At least 2 participants are required"
