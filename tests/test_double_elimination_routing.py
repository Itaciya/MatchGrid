from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.modules.match.models.match import Match
from app.modules.match.services.bracket_service import create_double_elimination_bracket
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

SIZES = [4, 8, 16, 32]
ALL_SIZES = SIZES


def _build(db, count):
    user = User(
        email=f"double_route_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()

    tournament = Tournament(
        name=f"Double Route {uuid4()}",
        description="Routing test",
        format="double_elimination",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=user.id,
        registration_open_at=datetime(2098, 12, 1, 0, 0, tzinfo=timezone.utc),
        registration_close_at=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc),
    )
    db.add(tournament)
    db.flush()

    teams = []
    for _ in range(count):
        team = Team(name=f"Double Route Team {uuid4()}", captain_id=user.id)
        db.add(team)
        teams.append(team)
    db.flush()

    rounds = create_double_elimination_bracket(
        db=db,
        tournament_id=tournament.id,
        participant_ids=[t.id for t in teams],
    )

    grid = {"winners": [], "losers": [], "final": []}
    for tournament_round in rounds:
        matches = (
            db.query(Match)
            .filter(Match.round_id == tournament_round.id)
            .order_by(Match.match_number)
            .all()
        )
        grid[tournament_round.bracket_type].append(matches)

    return grid


def _all(grid):
    return [m for kind in ("winners", "losers", "final") for r in grid[kind] for m in r]


def _feeder_counts(grid):
    counts = {m.id: {"winner": 0, "loser": 0} for m in _all(grid)}
    for m in _all(grid):
        if m.winner_next_match_id is not None:
            counts[m.winner_next_match_id]["winner"] += 1
        if m.loser_next_match_id is not None:
            counts[m.loser_next_match_id]["loser"] += 1
    return counts


# SCRUM-247: winners move correctly

@pytest.mark.parametrize("n", ALL_SIZES)
def test_winners_advance_to_the_next_winners_round_match(db, n):
    winners = _build(db, n)["winners"]

    for r in range(len(winners) - 1):
        for i, match in enumerate(winners[r]):
            assert match.winner_next_match_id == winners[r + 1][i // 2].id


@pytest.mark.parametrize("n", ALL_SIZES)
def test_winners_bracket_champion_goes_to_the_grand_final(db, n):
    grid = _build(db, n)

    assert grid["winners"][-1][0].winner_next_match_id == grid["final"][0][0].id


@pytest.mark.parametrize("n", ALL_SIZES)
def test_last_losers_match_feeds_the_grand_final(db, n):
    grid = _build(db, n)

    assert grid["losers"][-1][0].winner_next_match_id == grid["final"][0][0].id


# SCRUM-247: losers move to the correct bracket

@pytest.mark.parametrize("n", ALL_SIZES)
def test_every_winners_match_sends_its_loser_into_the_losers_bracket(db, n):
    grid = _build(db, n)
    losers_ids = {m.id for r in grid["losers"] for m in r}

    for r in grid["winners"]:
        for match in r:
            assert match.loser_next_match_id in losers_ids


@pytest.mark.parametrize("n", ALL_SIZES)
def test_first_round_losers_pair_up_in_the_first_losers_round(db, n):
    grid = _build(db, n)
    first_losers = grid["losers"][0]

    for i, match in enumerate(grid["winners"][0]):
        assert match.loser_next_match_id == first_losers[i // 2].id


@pytest.mark.parametrize("n", ALL_SIZES)
def test_later_winners_round_losers_drop_into_the_matching_losers_round(db, n):
    grid = _build(db, n)

    for w in range(1, len(grid["winners"])):
        target = grid["losers"][2 * w - 1]
        for i, match in enumerate(grid["winners"][w]):
            assert match.loser_next_match_id == target[i].id


@pytest.mark.parametrize("n", ALL_SIZES)
def test_winners_final_loser_goes_to_the_last_losers_round(db, n):
    grid = _build(db, n)

    assert grid["winners"][-1][0].loser_next_match_id == grid["losers"][-1][0].id


@pytest.mark.parametrize("n", ALL_SIZES)
def test_losers_to_the_losers_bracket_come_only_from_the_winners_bracket(db, n):
    grid = _build(db, n)
    winners_ids = {m.id for r in grid["winners"] for m in r}

    for match in _all(grid):
        for feeder in _all(grid):
            if feeder.loser_next_match_id == match.id:
                assert feeder.id in winners_ids


# SCRUM-247: eliminated teams cannot continue

@pytest.mark.parametrize("n", ALL_SIZES)
def test_a_loss_in_the_losers_bracket_eliminates_the_team(db, n):
    grid = _build(db, n)

    for r in grid["losers"]:
        assert all(m.loser_next_match_id is None for m in r)


@pytest.mark.parametrize("n", ALL_SIZES)
def test_grand_final_has_no_next_match_for_either_side(db, n):
    grand_final = _build(db, n)["final"][0][0]

    assert grand_final.winner_next_match_id is None
    assert grand_final.loser_next_match_id is None


@pytest.mark.parametrize("n", ALL_SIZES)
def test_every_winners_match_advances_its_winner(db, n):
    grid = _build(db, n)

    assert all(m.winner_next_match_id is not None for r in grid["winners"] for m in r)


@pytest.mark.parametrize("n", ALL_SIZES)
def test_every_losers_match_advances_its_winner(db, n):
    grid = _build(db, n)

    for r in grid["losers"]:
        for match in r:
            assert match.winner_next_match_id is not None


# SCRUM-247: bracket relationships remain valid

@pytest.mark.parametrize("n", ALL_SIZES)
def test_links_never_point_backwards_or_to_themselves(db, n):
    grid = _build(db, n)
    numbers = {m.id: m.match_number for m in _all(grid)}

    for match in _all(grid):
        for target in (match.winner_next_match_id, match.loser_next_match_id):
            if target is not None:
                assert target != match.id
                assert numbers[target] > match.match_number


@pytest.mark.parametrize("n", ALL_SIZES)
def test_all_links_stay_inside_the_same_tournament(db, n):
    grid = _build(db, n)
    ids = {m.id for m in _all(grid)}

    for match in _all(grid):
        for target in (match.winner_next_match_id, match.loser_next_match_id):
            assert target is None or target in ids


@pytest.mark.parametrize("n", ALL_SIZES)
def test_no_match_receives_more_than_two_entrants(db, n):
    grid = _build(db, n)

    for counts in _feeder_counts(grid).values():
        assert counts["winner"] + counts["loser"] <= 2


@pytest.mark.parametrize("n", ALL_SIZES)
def test_every_match_after_the_first_round_receives_exactly_two_entrants(db, n):
    grid = _build(db, n)
    counts = _feeder_counts(grid)
    first_round_ids = {m.id for m in grid["winners"][0]}

    for match in _all(grid):
        if match.id in first_round_ids:
            continue
        assert counts[match.id]["winner"] + counts[match.id]["loser"] == 2


@pytest.mark.parametrize("n", ALL_SIZES)
def test_first_losers_round_receives_two_winners_bracket_losers_per_match(db, n):
    grid = _build(db, n)
    counts = _feeder_counts(grid)

    for match in grid["losers"][0]:
        assert counts[match.id] == {"winner": 0, "loser": 2}


@pytest.mark.parametrize("n", ALL_SIZES)
def test_odd_losers_rounds_get_one_survivor_and_one_dropped_winners_loser(db, n):
    grid = _build(db, n)
    counts = _feeder_counts(grid)

    for index in range(1, len(grid["losers"]), 2):
        for match in grid["losers"][index]:
            assert counts[match.id] == {"winner": 1, "loser": 1}


@pytest.mark.parametrize("n", ALL_SIZES)
def test_halving_losers_rounds_pair_two_survivors_per_match(db, n):
    grid = _build(db, n)

    for index in range(1, len(grid["losers"]) - 1, 2):
        current, nxt = grid["losers"][index], grid["losers"][index + 1]
        if len(nxt) == len(current):
            continue
        for i, match in enumerate(current):
            assert match.winner_next_match_id == nxt[i // 2].id


# Two-team double elimination

def test_two_team_double_elimination_can_be_saved(db):
    grid = _build(db, 2)

    assert len(grid["winners"]) == 1
    assert len(grid["final"]) == 1


def test_two_team_grand_final_receives_both_teams_of_the_winners_match(db):
    grid = _build(db, 2)
    winners_match = grid["winners"][0][0]
    grand_final = grid["final"][0][0]

    assert grid["losers"] == []
    assert winners_match.winner_next_match_id == grand_final.id
    assert winners_match.loser_next_match_id == grand_final.id
