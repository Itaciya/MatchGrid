import time
from math import ceil, log2
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.match.models.match import Match
from app.modules.match.services.bracket_service import (
    create_double_elimination_bracket,
    generate_double_elimination_bracket,
    generate_single_elimination_bracket,
)
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

POW2_SIZES = [4, 8, 16, 32, 64, 128]
OK_SIZES = [3, 4, 7, 8, 15, 16, 31, 32, 64, 127, 128]
BUG_SIZES = [5, 6, 9, 10, 11, 12, 13, 14, 17, 33, 100]
ALL_SIZES = sorted(OK_SIZES + BUG_SIZES)


def _ids(n):
    return list(range(1, n + 1))


def _size(n):
    return 2 ** ceil(log2(n))


def _count(rounds):
    return sum(len(r) for r in rounds)


# SCRUM-247: winners bracket

@pytest.mark.parametrize("n", ALL_SIZES)
def test_winners_bracket_matches_the_single_elimination_bracket(n):
    bracket = generate_double_elimination_bracket(_ids(n))

    assert bracket["winners"] == generate_single_elimination_bracket(_ids(n))


@pytest.mark.parametrize("n", POW2_SIZES)
def test_winners_bracket_has_every_participant_once_and_a_single_final(n):
    winners = generate_double_elimination_bracket(_ids(n))["winners"]
    placed = [t for pair in winners[0] for t in pair if t is not None]

    assert placed == _ids(n)
    assert len(winners) == int(log2(n))
    assert winners[-1] == [(None, None)]


@pytest.mark.parametrize("n", ALL_SIZES)
def test_no_first_round_match_is_two_byes(n):
    first_round = generate_double_elimination_bracket(_ids(n))["winners"][0]

    assert (None, None) not in first_round


# SCRUM-247: losers bracket

@pytest.mark.parametrize("n", POW2_SIZES)
def test_losers_bracket_has_two_rounds_per_winners_round_after_the_first(n):
    losers = generate_double_elimination_bracket(_ids(n))["losers"]

    assert len(losers) == 2 * (int(log2(n)) - 1)


@pytest.mark.parametrize("n", POW2_SIZES)
def test_losers_rounds_come_in_equal_pairs_that_halve(n):
    losers = generate_double_elimination_bracket(_ids(n))["losers"]

    for pair_index in range(len(losers) // 2):
        expected = max(1, n // (2 ** (pair_index + 2)))
        assert len(losers[2 * pair_index]) == expected
        assert len(losers[2 * pair_index + 1]) == expected


@pytest.mark.parametrize("n", POW2_SIZES)
def test_match_counts_follow_the_double_elimination_formula(n):
    bracket = generate_double_elimination_bracket(_ids(n))

    assert _count(bracket["winners"]) == n - 1
    assert _count(bracket["losers"]) == n - 2
    assert _count(bracket["final"]) == 1
    assert (
        _count(bracket["winners"]) + _count(bracket["losers"]) + _count(bracket["final"])
        == 2 * n - 2
    )


@pytest.mark.parametrize("n", POW2_SIZES)
def test_first_losers_round_can_hold_every_first_round_loser(n):
    bracket = generate_double_elimination_bracket(_ids(n))

    # Each losers match takes two teams, so the first losers round holds n / 2 losers.
    assert len(bracket["losers"][0]) * 2 == len(bracket["winners"][0])


@pytest.mark.parametrize("n", [3, 5, 6, 7, 9, 12, 100])
def test_non_power_of_two_losers_bracket_depends_only_on_the_bracket_size(n):
    odd = generate_double_elimination_bracket(_ids(n))
    full = generate_double_elimination_bracket(_ids(_size(n)))

    assert odd["losers"] == full["losers"]
    assert odd["final"] == full["final"]


@pytest.mark.parametrize("n", ALL_SIZES)
def test_losers_and_final_matches_start_empty(n):
    bracket = generate_double_elimination_bracket(_ids(n))

    for stage in ("losers", "final"):
        for current_round in bracket[stage]:
            assert all(match == (None, None) for match in current_round)


# SCRUM-247: final

@pytest.mark.parametrize("n", ALL_SIZES)
def test_exactly_one_grand_final_match(n):
    bracket = generate_double_elimination_bracket(_ids(n))

    assert bracket["final"] == [[(None, None)]]


def test_two_teams_have_a_winners_match_a_final_and_no_losers_bracket():
    assert generate_double_elimination_bracket([1, 2]) == {
        "winners": [[(1, 2)]],
        "losers": [],
        "final": [[(None, None)]],
    }


# SCRUM-247: validation, determinism, large sizes

@pytest.mark.parametrize("ids", [[], [1]])
def test_fewer_than_two_participants_are_rejected(ids):
    with pytest.raises(ValueError, match="At least 2 participants"):
        generate_double_elimination_bracket(ids)


@pytest.mark.parametrize("ids", [[1, 1], [1, 2, 3, 1], [4, 4, 4]])
def test_duplicate_participants_are_rejected(ids):
    with pytest.raises(ValueError, match="Duplicate participants"):
        generate_double_elimination_bracket(ids)


def test_input_list_is_not_modified():
    ids = [5, 3, 9, 1, 7]
    snapshot = list(ids)

    generate_double_elimination_bracket(ids)

    assert ids == snapshot


@pytest.mark.parametrize("n", [3, 8, 13, 64])
def test_same_input_gives_the_same_bracket_every_time(n):
    first = generate_double_elimination_bracket(_ids(n))

    for _ in range(5):
        assert generate_double_elimination_bracket(_ids(n)) == first


def test_very_large_bracket_is_generated_quickly():
    started = time.perf_counter()
    bracket = generate_double_elimination_bracket(_ids(4096))
    elapsed = time.perf_counter() - started

    assert _count(bracket["winners"]) == 4095
    assert _count(bracket["losers"]) == 4094
    assert elapsed < 2.0


# SCRUM-247: saved bracket (database)

def _make_user(db):
    user = User(
        email=f"double_elim_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()
    return user


def _make_tournament(db, organizer_id, fmt="double_elimination"):
    tournament = Tournament(
        name=f"Double Elim Algo {uuid4()}",
        description="Algorithm test",
        format=fmt,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )
    db.add(tournament)
    db.flush()
    return tournament


def _make_teams(db, captain_id, count):
    teams = []
    for _ in range(count):
        team = Team(name=f"Double Elim Team {uuid4()}", captain_id=captain_id)
        db.add(team)
        teams.append(team)
    db.flush()
    return teams


def _build(db, count, fmt="double_elimination"):
    user = _make_user(db)
    tournament = _make_tournament(db, user.id, fmt)
    teams = _make_teams(db, user.id, count)
    rounds = create_double_elimination_bracket(
        db=db,
        tournament_id=tournament.id,
        participant_ids=[team.id for team in teams],
    )
    matches = (
        db.query(Match)
        .filter(Match.tournament_id == tournament.id)
        .order_by(Match.match_number)
        .all()
    )
    by_type = {
        kind: [m for m in matches if m.round.bracket_type == kind]
        for kind in ("winners", "losers", "final")
    }
    return tournament, teams, rounds, matches, by_type


@pytest.mark.parametrize("count,winners,losers", [(4, 3, 2), (8, 7, 6), (16, 15, 14)])
def test_saved_bracket_has_the_expected_match_counts(db, count, winners, losers):
    _, _, _, matches, by_type = _build(db, count)

    assert len(by_type["winners"]) == winners
    assert len(by_type["losers"]) == losers
    assert len(by_type["final"]) == 1
    assert len(matches) == 2 * count - 2


@pytest.mark.parametrize("count,expected_rounds", [(4, 5), (8, 8)])
def test_saved_bracket_creates_winners_losers_and_final_rounds(db, count, expected_rounds):
    _, _, rounds, _, _ = _build(db, count)

    assert len(rounds) == expected_rounds
    assert {r.bracket_type for r in rounds} == {"winners", "losers", "final"}


@pytest.mark.parametrize("count", [4, 8, 16])
def test_winners_final_and_losers_final_both_feed_the_grand_final(db, count):
    _, _, _, _, by_type = _build(db, count)
    grand_final = by_type["final"][0]

    assert by_type["winners"][-1].winner_next_match_id == grand_final.id
    assert by_type["losers"][-1].winner_next_match_id == grand_final.id


@pytest.mark.parametrize("count", [4, 8])
def test_grand_final_has_no_next_match(db, count):
    _, _, _, _, by_type = _build(db, count)
    grand_final = by_type["final"][0]

    assert grand_final.winner_next_match_id is None
    assert grand_final.loser_next_match_id is None


def test_saved_first_winners_round_pairs_teams_in_seed_order(db):
    _, teams, _, _, by_type = _build(db, 8)

    pairs = [(m.team_a_id, m.team_b_id) for m in by_type["winners"][:4]]

    assert pairs == [
        (teams[0].id, teams[1].id),
        (teams[2].id, teams[3].id),
        (teams[4].id, teams[5].id),
        (teams[6].id, teams[7].id),
    ]


def test_losers_and_final_matches_start_without_teams(db):
    _, _, _, _, by_type = _build(db, 8)

    for kind in ("losers", "final"):
        for match in by_type[kind]:
            assert match.team_a_id is None
            assert match.team_b_id is None


def test_no_team_appears_twice_in_the_saved_first_round(db):
    _, teams, _, _, by_type = _build(db, 8)
    placed = [
        t for m in by_type["winners"][:4] for t in (m.team_a_id, m.team_b_id)
    ]

    assert sorted(placed) == sorted(t.id for t in teams)


def test_wrong_format_is_rejected_and_nothing_is_saved(db):
    user = _make_user(db)
    tournament = _make_tournament(db, user.id, fmt="single_elimination")
    teams = _make_teams(db, user.id, 4)

    with pytest.raises(BadRequestException):
        create_double_elimination_bracket(
            db=db,
            tournament_id=tournament.id,
            participant_ids=[t.id for t in teams],
        )

    assert db.query(Match).filter(Match.tournament_id == tournament.id).count() == 0


def test_unknown_tournament_is_rejected(db):
    with pytest.raises(NotFoundException):
        create_double_elimination_bracket(
            db=db, tournament_id=999999999, participant_ids=[1, 2]
        )


@pytest.mark.parametrize("ids_factory", [lambda t: [t[0].id], lambda t: [t[0].id, t[0].id]])
def test_invalid_participants_are_rejected_when_saving(db, ids_factory):
    user = _make_user(db)
    tournament = _make_tournament(db, user.id)
    teams = _make_teams(db, user.id, 2)

    with pytest.raises(BadRequestException):
        create_double_elimination_bracket(
            db=db,
            tournament_id=tournament.id,
            participant_ids=ids_factory(teams),
        )

    assert db.query(Match).filter(Match.tournament_id == tournament.id).count() == 0


# Fix: byes are spread across separate first-round matches

@pytest.mark.parametrize("n", ALL_SIZES)
def test_every_first_round_match_has_at_least_one_team(n):
    for pair in generate_double_elimination_bracket(_ids(n))["winners"][0]:
        assert any(team is not None for team in pair)
