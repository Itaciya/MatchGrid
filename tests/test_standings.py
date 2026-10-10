import uuid
from datetime import datetime, timezone

from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.match.services.match_result_service import determine_outcome
from app.modules.match.services.standings_service import get_tournament_standings
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.score.models.score import Score
from app.modules.tournament.models.tournament import Tournament
from test_match_result_finalization import _make_user


def _make_tournament(db):
    organiser = _make_user(db, "organiser")
    tournament = Tournament(
        name=f"Standings Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament, organiser


def _make_team(db, captain_id):
    team = Team(
        name=f"Standings Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _add_match(db, tournament, team_a_id, team_b_id, number, status="completed"):
    match = Match(
        tournament_id=tournament.id,
        match_number=number,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        scheduled_at=datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        status=status,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def _play(db, tournament, organiser, number, team_a, team_b, a, b):
    """A completed match with a finalized result, written directly."""
    match = _add_match(db, tournament, team_a.id, team_b.id, number)
    outcome = determine_outcome(a, b)
    if outcome == "team_a_win":
        winner, loser = team_a.id, team_b.id
    elif outcome == "team_b_win":
        winner, loser = team_b.id, team_a.id
    else:
        winner = loser = None
    db.add(
        MatchResult(
            match_id=match.id,
            outcome=outcome,
            winner_team_id=winner,
            loser_team_id=loser,
            team_a_score=a,
            team_b_score=b,
            finalized_by_id=organiser.id,
            finalized_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return match


def _by_team(table):
    return {row["team_id"]: row for row in table}


def test_wins_draws_and_losses_score_three_one_zero(db):
    tournament, organiser = _make_tournament(db)
    a, b, c = [_make_team(db, organiser.id) for _ in range(3)]
    _play(db, tournament, organiser, 1, a, b, 2, 1)  # A beats B
    _play(db, tournament, organiser, 2, b, c, 1, 1)  # B draws C
    _play(db, tournament, organiser, 3, a, c, 0, 3)  # C beats A

    table = get_tournament_standings(db, tournament.id)

    assert [row["team_id"] for row in table] == [c.id, a.id, b.id]
    rows = _by_team(table)
    assert rows[c.id] == {
        "team_id": c.id, "played": 2, "wins": 1, "draws": 1, "losses": 0,
        "goals_for": 4, "goals_against": 1, "goal_difference": 3, "points": 4,
    }
    assert rows[a.id] == {
        "team_id": a.id, "played": 2, "wins": 1, "draws": 0, "losses": 1,
        "goals_for": 2, "goals_against": 4, "goal_difference": -2, "points": 3,
    }
    assert rows[b.id] == {
        "team_id": b.id, "played": 2, "wins": 0, "draws": 1, "losses": 1,
        "goals_for": 2, "goals_against": 3, "goal_difference": -1, "points": 1,
    }


def test_ties_on_points_are_broken_by_goal_difference(db):
    tournament, organiser = _make_tournament(db)
    p, q, r, s = [_make_team(db, organiser.id) for _ in range(4)]
    _play(db, tournament, organiser, 1, p, q, 5, 0)
    _play(db, tournament, organiser, 2, r, s, 1, 0)

    table = get_tournament_standings(db, tournament.id)

    assert [row["team_id"] for row in table] == [p.id, r.id, s.id, q.id]


def test_teams_level_on_everything_are_ordered_by_team_id(db):
    tournament, organiser = _make_tournament(db)
    x, y = [_make_team(db, organiser.id) for _ in range(2)]
    _play(db, tournament, organiser, 1, x, y, 1, 1)

    table = get_tournament_standings(db, tournament.id)

    assert [row["team_id"] for row in table] == sorted([x.id, y.id])


def test_teams_without_a_finalized_match_are_listed_with_zeroes(db):
    tournament, organiser = _make_tournament(db)
    d, e = [_make_team(db, organiser.id) for _ in range(2)]
    _add_match(db, tournament, d.id, e.id, 1, status="scheduled")

    rows = _by_team(get_tournament_standings(db, tournament.id))

    assert set(rows) == {d.id, e.id}
    for row in rows.values():
        assert row["played"] == 0
        assert row["points"] == 0
        assert row["goal_difference"] == 0


def test_a_verified_score_without_a_finalized_result_does_not_count(db):
    tournament, organiser = _make_tournament(db)
    d, e = [_make_team(db, organiser.id) for _ in range(2)]
    match = _add_match(db, tournament, d.id, e.id, 1, status="live")
    db.add(
        Score(
            match_id=match.id,
            team_a_score=5,
            team_b_score=0,
            verification_status="verified",
            is_verified=True,
        )
    )
    db.commit()

    rows = _by_team(get_tournament_standings(db, tournament.id))

    assert rows[d.id]["played"] == 0
    assert rows[d.id]["points"] == 0


def test_other_tournaments_do_not_affect_standings(db):
    first, organiser = _make_tournament(db)
    second, other_organiser = _make_tournament(db)
    a, b = [_make_team(db, organiser.id) for _ in range(2)]
    c, d = [_make_team(db, other_organiser.id) for _ in range(2)]
    _play(db, first, organiser, 1, a, b, 1, 0)
    _play(db, second, other_organiser, 1, c, d, 4, 0)

    first_table = get_tournament_standings(db, first.id)
    second_table = get_tournament_standings(db, second.id)

    assert {row["team_id"] for row in first_table} == {a.id, b.id}
    assert {row["team_id"] for row in second_table} == {c.id, d.id}
    assert _by_team(first_table)[a.id]["goals_for"] == 1


def test_matches_without_both_teams_are_ignored(db):
    tournament, organiser = _make_tournament(db)
    a = _make_team(db, organiser.id)
    _add_match(db, tournament, a.id, None, 1, status="scheduled")
    _add_match(db, tournament, None, None, 2, status="scheduled")

    table = get_tournament_standings(db, tournament.id)

    assert [row["team_id"] for row in table] == [a.id]
    assert table[0]["played"] == 0


def test_unknown_tournament_has_empty_standings(db):
    assert get_tournament_standings(db, 2_000_000_000) == []
