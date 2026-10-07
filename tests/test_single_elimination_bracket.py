from datetime import datetime, timezone
from uuid import uuid4

from app.modules.match.models.match import Match
from app.modules.match.models.tournament_round import TournamentRound
from app.modules.match.services.bracket_service import (
    create_double_elimination_bracket,
    create_single_elimination_bracket,
    create_tournament_rounds,
    generate_double_elimination_bracket,
    generate_round_names,
    generate_single_elimination_bracket,
)
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def test_single_elimination_two_participants():
    result = generate_single_elimination_bracket([1, 2])

    assert result == [
        [(1, 2)],
    ]


def test_single_elimination_four_participants():
    result = generate_single_elimination_bracket([1, 2, 3, 4])

    assert result == [
        [(1, 2), (3, 4)],
        [(None, None)],
    ]


def test_single_elimination_three_participants_has_bye():
    result = generate_single_elimination_bracket([1, 2, 3])

    assert result == [
        [(1, 2), (3, None)],
        [(None, None)],
    ]


def test_single_elimination_rejects_less_than_two():
    try:
        generate_single_elimination_bracket([1])
        assert False
    except ValueError as exc:
        assert str(exc) == "At least 2 participants are required"


def test_single_elimination_rejects_duplicates():
    try:
        generate_single_elimination_bracket([1, 2, 2, 3])
        assert False
    except ValueError as exc:
        assert str(exc) == "Duplicate participants are not allowed"


def test_double_elimination_four_participants():
    result = generate_double_elimination_bracket(
        [1, 2, 3, 4]
    )

    assert result == {
        "winners": [
            [(1, 2), (3, 4)],
            [(None, None)],
        ],
        "losers": [
            [(None, None)],
            [(None, None)],
        ],
        "final": [
            [(None, None)],
        ],
    }


def test_double_elimination_eight_participants():
    result = generate_double_elimination_bracket(
        [1, 2, 3, 4, 5, 6, 7, 8]
    )

    assert result == {
        "winners": [
            [
                (1, 2),
                (3, 4),
                (5, 6),
                (7, 8),
            ],
            [
                (None, None),
                (None, None),
            ],
            [
                (None, None),
            ],
        ],
        "losers": [
            [
                (None, None),
                (None, None),
            ],
            [
                (None, None),
                (None, None),
            ],
            [
                (None, None),
            ],
            [
                (None, None),
            ],
        ],
        "final": [
            [(None, None)],
        ],
    }


def test_double_elimination_supports_byes():
    result = generate_double_elimination_bracket(
        [1, 2, 3]
    )

    assert result["winners"][0] == [
        (1, 2),
        (3, None),
    ]

    assert len(result["winners"]) == 2
    assert len(result["losers"]) == 2

    assert result["final"] == [
        [(None, None)],
    ]


def test_double_elimination_rejects_less_than_two():
    try:
        generate_double_elimination_bracket([1])
        assert False
    except ValueError as exc:
        assert str(exc) == "At least 2 participants are required"


def test_double_elimination_rejects_duplicates():
    try:
        generate_double_elimination_bracket(
            [1, 2, 2, 3]
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "Duplicate participants are not allowed"


def test_generate_round_names():
    assert generate_round_names(3) == [
        "Round 1",
        "Round 2",
        "Round 3",
    ]


def test_generate_round_names_supports_more_than_five_rounds():
    assert generate_round_names(6) == [
        "Round 1",
        "Round 2",
        "Round 3",
        "Round 4",
        "Round 5",
        "Round 6",
    ]


def test_generate_round_names_rejects_zero():
    try:
        generate_round_names(0)
        assert False
    except ValueError as exc:
        assert str(exc) == "At least 1 round is required"


def _make_bracket_user(db):
    user = User(
        email=f"bracket_test_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )

    db.add(user)
    db.flush()

    return user


def _make_bracket_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"Single Elimination Test {uuid4()}",
        description="Bracket integration test",
        format="single_elimination",
        start_date=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        end_date=datetime(
            2026,
            1,
            10,
            tzinfo=timezone.utc,
        ),
        status="upcoming",
        organizer_id=organizer_id,
    )

    db.add(tournament)
    db.flush()

    return tournament


def _make_bracket_team(db, captain_id):
    team = Team(
        name=f"Bracket Test Team {uuid4()}",
        captain_id=captain_id,
    )

    db.add(team)
    db.flush()

    return team


def test_create_single_elimination_bracket_creates_all_matches(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    teams = [
        _make_bracket_team(db, user.id)
        for _ in range(4)
    ]

    rounds = create_single_elimination_bracket(
        db=db,
        tournament_id=tournament.id,
        participant_ids=[team.id for team in teams],
    )

    assert len(rounds) == 2

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament.id
        )
        .order_by(Match.id)
        .all()
    )

    assert len(matches) == 3

    first_round_matches = [
        match
        for match in matches
        if match.round_id == rounds[0].id
    ]

    final_matches = [
        match
        for match in matches
        if match.round_id == rounds[1].id
    ]

    assert len(first_round_matches) == 2
    assert len(final_matches) == 1

    final = final_matches[0]

    assert all(
        match.winner_next_match_id == final.id
        for match in first_round_matches
    )


def test_create_single_elimination_bracket_handles_bye(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    teams = [
        _make_bracket_team(db, user.id)
        for _ in range(3)
    ]

    create_single_elimination_bracket(
        db=db,
        tournament_id=tournament.id,
        participant_ids=[team.id for team in teams],
    )

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament.id
        )
        .order_by(Match.id)
        .all()
    )

    assert len(matches) == 3

    final = matches[-1]

    assert (
        final.team_a_id == teams[2].id
        or final.team_b_id == teams[2].id
    )


def test_create_single_elimination_bracket_rejects_wrong_format(db):
    user = _make_bracket_user(db)

    tournament = Tournament(
        name=f"Round Robin Test {uuid4()}",
        description="Wrong format test",
        format="round_robin",
        start_date=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        end_date=datetime(
            2026,
            1,
            10,
            tzinfo=timezone.utc,
        ),
        status="upcoming",
        organizer_id=user.id,
    )

    db.add(tournament)
    db.flush()

    try:
        create_single_elimination_bracket(
            db=db,
            tournament_id=tournament.id,
            participant_ids=[1, 2],
        )
        assert False
    except Exception as exc:
        assert "single_elimination" in str(exc)


def test_tournament_round_relationship_contains_created_matches(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    teams = [
        _make_bracket_team(db, user.id)
        for _ in range(4)
    ]

    rounds = create_single_elimination_bracket(
        db=db,
        tournament_id=tournament.id,
        participant_ids=[team.id for team in teams],
    )

    db.refresh(rounds[0])
    db.refresh(rounds[1])

    assert len(rounds[0].matches) == 2
    assert len(rounds[1].matches) == 1

    assert all(
        isinstance(match, Match)
        for match in rounds[0].matches
        + rounds[1].matches
    )


def test_create_double_elimination_bracket_creates_all_matches(db):
    user = _make_bracket_user(db)

    tournament = Tournament(
        name=f"Double Elimination Test {uuid4()}",
        description="Double elimination integration test",
        format="double_elimination",
        start_date=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        end_date=datetime(
            2026,
            1,
            10,
            tzinfo=timezone.utc,
        ),
        status="upcoming",
        organizer_id=user.id,
    )

    db.add(tournament)
    db.flush()

    teams = [
        _make_bracket_team(db, user.id)
        for _ in range(4)
    ]

    rounds = create_double_elimination_bracket(
        db=db,
        tournament_id=tournament.id,
        participant_ids=[team.id for team in teams],
    )

    assert len(rounds) == 5

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament.id
        )
        .order_by(Match.id)
        .all()
    )

    assert len(matches) == 6

    winners_matches = [
        match
        for match in matches
        if match.round.bracket_type == "winners"
    ]

    losers_matches = [
        match
        for match in matches
        if match.round.bracket_type == "losers"
    ]

    final_matches = [
        match
        for match in matches
        if match.round.bracket_type == "final"
    ]

    assert len(winners_matches) == 3
    assert len(losers_matches) == 2
    assert len(final_matches) == 1

    winners_final = winners_matches[-1]
    grand_final = final_matches[0]

    assert winners_final.winner_next_match_id == grand_final.id

    assert losers_matches[-1].winner_next_match_id == (
        grand_final.id
    )


def test_create_tournament_rounds_creates_ordered_rounds(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    rounds = create_tournament_rounds(
        db=db,
        tournament_id=tournament.id,
        number_of_rounds=4,
    )

    assert len(rounds) == 4

    assert [
        tournament_round.round_number
        for tournament_round in rounds
    ] == [1, 2, 3, 4]

    assert [
        tournament_round.name
        for tournament_round in rounds
    ] == [
        "Round 1",
        "Round 2",
        "Round 3",
        "Round 4",
    ]

    assert all(
        tournament_round.tournament_id == tournament.id
        for tournament_round in rounds
    )

    assert all(
        tournament_round.bracket_type == "main"
        for tournament_round in rounds
    )


def test_create_tournament_rounds_supports_custom_bracket_type(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    rounds = create_tournament_rounds(
        db=db,
        tournament_id=tournament.id,
        number_of_rounds=3,
        bracket_type="losers",
    )

    assert len(rounds) == 3

    assert all(
        tournament_round.bracket_type == "losers"
        for tournament_round in rounds
    )


def test_create_tournament_rounds_rejects_invalid_round_count(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    try:
        create_tournament_rounds(
            db=db,
            tournament_id=tournament.id,
            number_of_rounds=0,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "At least 1 round is required"


def test_create_tournament_rounds_rejects_invalid_tournament_id(db):
    try:
        create_tournament_rounds(
            db=db,
            tournament_id=0,
            number_of_rounds=2,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "Invalid tournament ID"


def test_create_tournament_rounds_rejects_empty_bracket_type(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    try:
        create_tournament_rounds(
            db=db,
            tournament_id=tournament.id,
            number_of_rounds=2,
            bracket_type="   ",
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "Bracket type is required"


def test_tournament_rounds_relationship_with_tournament(db):
    user = _make_bracket_user(db)

    tournament = _make_bracket_tournament(
        db,
        user.id,
    )

    rounds = create_tournament_rounds(
        db=db,
        tournament_id=tournament.id,
        number_of_rounds=3,
    )

    db.commit()
    db.refresh(tournament)

    assert len(tournament.rounds) == 3

    assert [
        tournament_round.round_number
        for tournament_round in tournament.rounds
    ] == [1, 2, 3]

    assert all(
        isinstance(tournament_round, TournamentRound)
        for tournament_round in tournament.rounds
    )