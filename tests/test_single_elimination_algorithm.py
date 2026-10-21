import time
from math import ceil, log2
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.match.models.match import Match
from app.modules.match.services.bracket_service import (
    create_single_elimination_bracket,
    generate_single_elimination_bracket,
)
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

BYE_BUG = pytest.mark.xfail(
    strict=True,
    reason="Byes are appended at the end, so 2+ byes create a (None, None) first-round match",
)

# Sizes with at most one bye work today.
OK_SIZES = [2, 3, 4, 7, 8, 15, 16, 31, 32, 64, 127, 128]
# Sizes with two or more byes hit the bye-placement bug.
BUG_SIZES = [5, 6, 9, 10, 11, 12, 13, 14, 17, 33, 100]
ALL_SIZES = sorted(OK_SIZES + BUG_SIZES)


def _ids(n):
    return list(range(1, n + 1))


def _size(n):
    return 2 ** ceil(log2(n))


# SCRUM-246: bracket generation and round counts

@pytest.mark.parametrize("n", ALL_SIZES)
def test_number_of_rounds_matches_the_bracket_size(n):
    bracket = generate_single_elimination_bracket(_ids(n))

    assert len(bracket) == ceil(log2(n))


@pytest.mark.parametrize("n", ALL_SIZES)
def test_each_round_has_half_the_matches_of_the_previous_round(n):
    bracket = generate_single_elimination_bracket(_ids(n))
    size = _size(n)

    for index, current_round in enumerate(bracket):
        assert len(current_round) == size // (2 ** (index + 1))


@pytest.mark.parametrize("n", ALL_SIZES)
def test_total_match_count_is_bracket_size_minus_one(n):
    bracket = generate_single_elimination_bracket(_ids(n))

    assert sum(len(r) for r in bracket) == _size(n) - 1


@pytest.mark.parametrize("n", ALL_SIZES)
def test_final_round_is_a_single_empty_match(n):
    bracket = generate_single_elimination_bracket(_ids(n))

    if len(bracket) == 1:
        assert len(bracket[0]) == 1
    else:
        assert bracket[-1] == [(None, None)]


@pytest.mark.parametrize("n", ALL_SIZES)
def test_later_rounds_start_empty_until_winners_advance(n):
    bracket = generate_single_elimination_bracket(_ids(n))

    for later_round in bracket[1:]:
        assert all(match == (None, None) for match in later_round)


# SCRUM-246: pairing and byes

@pytest.mark.parametrize("n", ALL_SIZES)
def test_every_participant_is_placed_in_round_one_exactly_once_in_order(n):
    ids = _ids(n)
    bracket = generate_single_elimination_bracket(ids)
    placed = [team for pair in bracket[0] for team in pair if team is not None]

    assert placed == ids


@pytest.mark.parametrize("n", ALL_SIZES)
def test_bye_count_fills_the_bracket_to_a_power_of_two(n):
    bracket = generate_single_elimination_bracket(_ids(n))
    byes = sum(1 for pair in bracket[0] for team in pair if team is None)

    assert byes == _size(n) - n


@pytest.mark.parametrize("n", ALL_SIZES)
def test_no_team_is_paired_with_itself(n):
    for first, second in generate_single_elimination_bracket(_ids(n))[0]:
        if first is not None:
            assert first != second


def test_non_sequential_ids_keep_their_order():
    ids = [90, 12, 7, 55, 3]
    placed = [
        team
        for pair in generate_single_elimination_bracket(ids)[0]
        for team in pair
        if team is not None
    ]

    assert placed == ids


def test_seven_teams_have_a_single_bye_for_the_last_seed():
    assert generate_single_elimination_bracket(_ids(7))[0] == [
        (1, 2),
        (3, 4),
        (5, 6),
        (7, None),
    ]


@pytest.mark.parametrize(
    "n",
    [pytest.param(n, marks=BYE_BUG) if n in BUG_SIZES else n for n in ALL_SIZES],
)
def test_no_first_round_match_is_two_byes(n):
    first_round = generate_single_elimination_bracket(_ids(n))[0]

    assert (None, None) not in first_round


# SCRUM-246: validation, determinism, large sizes

@pytest.mark.parametrize("ids", [[], [1]])
def test_fewer_than_two_participants_are_rejected(ids):
    with pytest.raises(ValueError, match="At least 2 participants"):
        generate_single_elimination_bracket(ids)


@pytest.mark.parametrize("ids", [[1, 1], [1, 2, 3, 1], [4, 4, 4]])
def test_duplicate_participants_are_rejected(ids):
    with pytest.raises(ValueError, match="Duplicate participants"):
        generate_single_elimination_bracket(ids)


def test_input_list_is_not_modified():
    ids = [5, 3, 9, 1, 7]
    snapshot = list(ids)

    generate_single_elimination_bracket(ids)

    assert ids == snapshot


@pytest.mark.parametrize("n", [3, 8, 13, 64])
def test_same_input_gives_the_same_bracket_every_time(n):
    first = generate_single_elimination_bracket(_ids(n))

    for _ in range(5):
        assert generate_single_elimination_bracket(_ids(n)) == first


def test_very_large_bracket_is_generated_quickly():
    started = time.perf_counter()
    bracket = generate_single_elimination_bracket(_ids(5000))
    elapsed = time.perf_counter() - started

    assert len(bracket) == 13
    assert sum(len(r) for r in bracket) == 8192 - 1
    assert elapsed < 2.0


# SCRUM-246: saved bracket, winner progression, final (database)

def _make_user(db):
    user = User(
        email=f"single_elim_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()
    return user


def _make_tournament(db, organizer_id, fmt="single_elimination"):
    tournament = Tournament(
        name=f"Single Elim Algo {uuid4()}",
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
        team = Team(name=f"Single Elim Team {uuid4()}", captain_id=captain_id)
        db.add(team)
        teams.append(team)
    db.flush()
    return teams


def _build(db, count, fmt="single_elimination"):
    user = _make_user(db)
    tournament = _make_tournament(db, user.id, fmt)
    teams = _make_teams(db, user.id, count)
    rounds = create_single_elimination_bracket(
        db=db,
        tournament_id=tournament.id,
        participant_ids=[team.id for team in teams],
    )
    matches_by_round = [
        db.query(Match)
        .filter(Match.round_id == r.id)
        .order_by(Match.match_number)
        .all()
        for r in rounds
    ]
    return tournament, teams, rounds, matches_by_round


@pytest.mark.parametrize("count", [2, 4, 8, 16])
def test_saved_bracket_has_the_expected_rounds_and_matches(db, count):
    _, _, rounds, matches_by_round = _build(db, count)

    assert len(rounds) == ceil(log2(count))
    assert [len(m) for m in matches_by_round] == [
        count // (2 ** (i + 1)) for i in range(len(rounds))
    ]
    assert all(m.status == "scheduled" for r in matches_by_round for m in r)


def test_saved_first_round_pairs_teams_in_seed_order(db):
    _, teams, _, matches_by_round = _build(db, 8)

    pairs = [(m.team_a_id, m.team_b_id) for m in matches_by_round[0]]

    assert pairs == [
        (teams[0].id, teams[1].id),
        (teams[2].id, teams[3].id),
        (teams[4].id, teams[5].id),
        (teams[6].id, teams[7].id),
    ]


@pytest.mark.parametrize("count", [4, 8, 16])
def test_winners_progress_to_the_next_round_match(db, count):
    _, _, _, matches_by_round = _build(db, count)

    for round_index in range(len(matches_by_round) - 1):
        next_round = matches_by_round[round_index + 1]
        for match_index, match in enumerate(matches_by_round[round_index]):
            assert match.winner_next_match_id == next_round[match_index // 2].id


@pytest.mark.parametrize("count", [2, 4, 8, 16])
def test_final_is_a_single_match_with_no_next_match(db, count):
    _, _, _, matches_by_round = _build(db, count)

    assert len(matches_by_round[-1]) == 1
    assert matches_by_round[-1][0].winner_next_match_id is None


def test_later_round_matches_start_without_teams(db):
    _, _, _, matches_by_round = _build(db, 8)

    for later_round in matches_by_round[1:]:
        for match in later_round:
            assert match.team_a_id is None
            assert match.team_b_id is None


def test_single_elimination_has_no_loser_routing(db):
    _, _, _, matches_by_round = _build(db, 8)

    assert all(m.loser_next_match_id is None for r in matches_by_round for m in r)


def test_seven_teams_bye_team_advances_to_the_correct_second_round_match(db):
    _, teams, _, matches_by_round = _build(db, 7)

    bye_match = matches_by_round[0][3]
    second_round_match = matches_by_round[1][1]

    assert bye_match.team_a_id == teams[6].id
    assert bye_match.team_b_id is None
    assert teams[6].id in (second_round_match.team_a_id, second_round_match.team_b_id)


def test_three_teams_bye_team_is_placed_in_the_final(db):
    _, teams, _, matches_by_round = _build(db, 3)

    final = matches_by_round[-1][0]

    assert teams[2].id in (final.team_a_id, final.team_b_id)


def test_wrong_format_is_rejected_and_nothing_is_saved(db):
    user = _make_user(db)
    tournament = _make_tournament(db, user.id, fmt="round_robin")
    teams = _make_teams(db, user.id, 4)

    with pytest.raises(BadRequestException):
        create_single_elimination_bracket(
            db=db,
            tournament_id=tournament.id,
            participant_ids=[t.id for t in teams],
        )

    assert db.query(Match).filter(Match.tournament_id == tournament.id).count() == 0


def test_unknown_tournament_is_rejected(db):
    with pytest.raises(NotFoundException):
        create_single_elimination_bracket(
            db=db, tournament_id=999999999, participant_ids=[1, 2]
        )


@pytest.mark.parametrize("ids_factory", [lambda t: [t[0].id], lambda t: [t[0].id, t[0].id]])
def test_invalid_participants_are_rejected_when_saving(db, ids_factory):
    user = _make_user(db)
    tournament = _make_tournament(db, user.id)
    teams = _make_teams(db, user.id, 2)

    with pytest.raises(BadRequestException):
        create_single_elimination_bracket(
            db=db,
            tournament_id=tournament.id,
            participant_ids=ids_factory(teams),
        )

    assert db.query(Match).filter(Match.tournament_id == tournament.id).count() == 0