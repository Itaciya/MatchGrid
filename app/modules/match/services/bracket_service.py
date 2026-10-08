from math import ceil, log2

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.match.models.match import Match
from app.modules.match.models.tournament_round import TournamentRound
from app.modules.match.services.match_number_service import (
    get_next_match_number,
)
from app.modules.tournament.models.tournament import Tournament


ROUND_NAMES = {
    1: "Round 1",
    2: "Round 2",
    3: "Round 3",
    4: "Round 4",
    5: "Round 5",
}


def generate_single_elimination_bracket(
    participant_ids: list[int],
) -> list[list[tuple[int | None, int | None]]]:
    """Generate a single-elimination bracket with required bye positions."""

    if len(participant_ids) < 2:
        raise ValueError("At least 2 participants are required")

    participants = list(dict.fromkeys(participant_ids))

    if len(participants) != len(participant_ids):
        raise ValueError("Duplicate participants are not allowed")

    bracket_size = 2 ** ceil(log2(len(participants)))
    bye_count = bracket_size - len(participants)

    seeded_participants = participants + [None] * bye_count

    rounds: list[list[tuple[int | None, int | None]]] = []

    current_round = [
        (
            seeded_participants[index],
            seeded_participants[index + 1],
        )
        for index in range(0, bracket_size, 2)
    ]

    rounds.append(current_round)

    match_count = len(current_round) // 2

    while match_count >= 1:
        rounds.append(
            [(None, None) for _ in range(match_count)]
        )
        match_count //= 2

    return rounds


def generate_round_names(number_of_rounds: int) -> list[str]:
    """Generate ordered names for tournament rounds."""

    if number_of_rounds < 1:
        raise ValueError("At least 1 round is required")

    return [
        ROUND_NAMES.get(
            round_number,
            f"Round {round_number}",
        )
        for round_number in range(1, number_of_rounds + 1)
    ]


def create_tournament_rounds(
    db: Session,
    tournament_id: int,
    number_of_rounds: int,
    bracket_type: str = "main",
) -> list[TournamentRound]:
    """Create ordered rounds for a tournament bracket."""

    if tournament_id <= 0:
        raise ValueError("Invalid tournament ID")

    if number_of_rounds < 1:
        raise ValueError("At least 1 round is required")

    if not bracket_type.strip():
        raise ValueError("Bracket type is required")

    round_names = generate_round_names(number_of_rounds)

    rounds = [
        TournamentRound(
            tournament_id=tournament_id,
            round_number=round_number,
            name=round_names[round_number - 1],
            bracket_type=bracket_type,
        )
        for round_number in range(1, number_of_rounds + 1)
    ]

    db.add_all(rounds)
    db.flush()

    return rounds


def advance_bye_participants(
    matches_by_round: list[list[Match]],
    bracket: list[list[tuple[int | None, int | None]]],
) -> None:
    """Advance first-round participants directly when their opponent is a bye."""

    if len(bracket) < 2:
        return

    first_round = bracket[0]
    next_round_matches = matches_by_round[1]

    for pairing_index, (team_a_id, team_b_id) in enumerate(first_round):
        if team_a_id is None and team_b_id is None:
            continue

        if team_a_id is not None and team_b_id is not None:
            continue

        participant_id = team_a_id or team_b_id

        if participant_id is None:
            continue

        next_match_index = pairing_index // 2

        if next_match_index >= len(next_round_matches):
            continue

        next_match = next_round_matches[next_match_index]

        if next_match.team_a_id is None:
            next_match.team_a_id = participant_id
        elif next_match.team_b_id is None:
            next_match.team_b_id = participant_id


def create_single_elimination_bracket(
    db: Session,
    tournament_id: int,
    participant_ids: list[int],
) -> list[TournamentRound]:
    """Create a complete single-elimination bracket."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(
            detail="Tournament not found"
        )

    if tournament.format != "single_elimination":
        raise BadRequestException(
            detail=(
                "Single-elimination bracket requires "
                "a single_elimination tournament"
            )
        )

    try:
        bracket = generate_single_elimination_bracket(
            participant_ids
        )
    except ValueError as exc:
        raise BadRequestException(
            detail=str(exc)
        ) from exc

    number_of_rounds = len(bracket)

    rounds = create_tournament_rounds(
        db=db,
        tournament_id=tournament_id,
        number_of_rounds=number_of_rounds,
    )

    matches_by_round: list[list[Match]] = []

    next_match_number = get_next_match_number(
        db,
        tournament_id,
    )

    for round_index, pairings in enumerate(bracket):
        current_round_matches: list[Match] = []

        for team_a_id, team_b_id in pairings:
            match = Match(
                tournament_id=tournament_id,
                match_number=next_match_number,
                round_id=rounds[round_index].id,
                team_a_id=team_a_id,
                team_b_id=team_b_id,
                scheduled_at=tournament.start_date,
                status="scheduled",
            )

            db.add(match)
            current_round_matches.append(match)

            next_match_number += 1

        matches_by_round.append(current_round_matches)

    db.flush()

    for round_index in range(len(matches_by_round) - 1):
        current_matches = matches_by_round[round_index]
        next_matches = matches_by_round[round_index + 1]

        for match_index, match in enumerate(current_matches):
            next_match_index = match_index // 2

            match.winner_next_match_id = (
                next_matches[next_match_index].id
            )

    advance_bye_participants(
        matches_by_round,
        bracket,
    )

    db.commit()

    for tournament_round in rounds:
        db.refresh(tournament_round)

    return rounds


def generate_double_elimination_bracket(
    participant_ids: list[int],
) -> dict[str, list[list[tuple[int | None, int | None]]]]:
    """Generate winners, losers, and final brackets for double elimination."""

    if len(participant_ids) < 2:
        raise ValueError("At least 2 participants are required")

    participants = list(dict.fromkeys(participant_ids))

    if len(participants) != len(participant_ids):
        raise ValueError("Duplicate participants are not allowed")

    bracket_size = 2 ** ceil(log2(len(participants)))
    bye_count = bracket_size - len(participants)

    seeded_participants = participants + [None] * bye_count

    winners_rounds: list[
        list[tuple[int | None, int | None]]
    ] = []

    first_round = [
        (
            seeded_participants[index],
            seeded_participants[index + 1],
        )
        for index in range(0, bracket_size, 2)
    ]

    winners_rounds.append(first_round)

    match_count = len(first_round) // 2

    while match_count >= 1:
        winners_rounds.append(
            [(None, None) for _ in range(match_count)]
        )
        match_count //= 2

    losers_rounds: list[
        list[tuple[int | None, int | None]]
    ] = []

    for winners_round_index in range(
        len(winners_rounds) - 1
    ):
        winners_matches = len(
            winners_rounds[winners_round_index]
        )

        losers_match_count = max(
            1,
            winners_matches // 2,
        )

        losers_rounds.append(
            [
                (None, None)
                for _ in range(losers_match_count)
            ]
        )

        losers_rounds.append(
            [
                (None, None)
                for _ in range(losers_match_count)
            ]
        )

    final_round = [
        [(None, None)]
    ]

    return {
        "winners": winners_rounds,
        "losers": losers_rounds,
        "final": final_round,
    }


def create_double_elimination_bracket(
    db: Session,
    tournament_id: int,
    participant_ids: list[int],
) -> list[TournamentRound]:
    """Create a complete double-elimination bracket."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(
            detail="Tournament not found"
        )

    if tournament.format != "double_elimination":
        raise BadRequestException(
            detail=(
                "Double-elimination bracket requires "
                "a double_elimination tournament"
            )
        )

    try:
        bracket = generate_double_elimination_bracket(
            participant_ids
        )
    except ValueError as exc:
        raise BadRequestException(
            detail=str(exc)
        ) from exc

    winners_bracket = bracket["winners"]
    losers_bracket = bracket["losers"]
    final_bracket = bracket["final"]

    winners_rounds = create_tournament_rounds(
        db=db,
        tournament_id=tournament_id,
        number_of_rounds=len(winners_bracket),
        bracket_type="winners",
    )

    losers_rounds = create_tournament_rounds(
        db=db,
        tournament_id=tournament_id,
        number_of_rounds=len(losers_bracket),
        bracket_type="losers",
    )

    final_rounds = create_tournament_rounds(
        db=db,
        tournament_id=tournament_id,
        number_of_rounds=len(final_bracket),
        bracket_type="final",
    )

    next_match_number = get_next_match_number(
        db,
        tournament_id,
    )

    winners_matches: list[list[Match]] = []

    for round_index, pairings in enumerate(winners_bracket):
        current_matches: list[Match] = []

        for team_a_id, team_b_id in pairings:
            match = Match(
                tournament_id=tournament_id,
                match_number=next_match_number,
                round_id=winners_rounds[round_index].id,
                team_a_id=team_a_id,
                team_b_id=team_b_id,
                scheduled_at=tournament.start_date,
                status="scheduled",
            )

            db.add(match)
            current_matches.append(match)

            next_match_number += 1

        winners_matches.append(current_matches)

    losers_matches: list[list[Match]] = []

    for round_index, pairings in enumerate(losers_bracket):
        current_matches: list[Match] = []

        for team_a_id, team_b_id in pairings:
            match = Match(
                tournament_id=tournament_id,
                match_number=next_match_number,
                round_id=losers_rounds[round_index].id,
                team_a_id=team_a_id,
                team_b_id=team_b_id,
                scheduled_at=tournament.start_date,
                status="scheduled",
            )

            db.add(match)
            current_matches.append(match)

            next_match_number += 1

        losers_matches.append(current_matches)

    final_matches: list[Match] = []

    for pairings in final_bracket:
        for team_a_id, team_b_id in pairings:
            match = Match(
                tournament_id=tournament_id,
                match_number=next_match_number,
                round_id=final_rounds[0].id,
                team_a_id=team_a_id,
                team_b_id=team_b_id,
                scheduled_at=tournament.start_date,
                status="scheduled",
            )

            db.add(match)
            final_matches.append(match)

            next_match_number += 1

    db.flush()

    # Winners bracket progression.
    for round_index in range(len(winners_matches) - 1):
        current_matches = winners_matches[round_index]
        next_matches = winners_matches[round_index + 1]

        for match_index, match in enumerate(current_matches):
            next_match_index = match_index // 2

            match.winner_next_match_id = (
                next_matches[next_match_index].id
            )

    # Winners-bracket losers drop into the losers bracket.
    if winners_matches:
        first_winners_round = winners_matches[0]

        if losers_matches:
            first_losers_round = losers_matches[0]

            for match_index, match in enumerate(
                first_winners_round
            ):
                loser_match_index = match_index // 2

                if loser_match_index < len(first_losers_round):
                    match.loser_next_match_id = (
                        first_losers_round[
                            loser_match_index
                        ].id
                    )

    # Winners of the first losers round advance
    # to the second losers round.
    for round_index in range(
        0,
        len(losers_matches) - 1,
        2,
    ):
        first_losers_round = losers_matches[round_index]
        second_losers_round = losers_matches[round_index + 1]

        for match_index, match in enumerate(
            first_losers_round
        ):
            if match_index < len(second_losers_round):
                match.winner_next_match_id = (
                    second_losers_round[
                        match_index
                    ].id
                )

    # Later losers rounds receive the winners
    # of the previous losers round and losers
    # from the next winners round.
    for losers_round_index in range(
        1,
        len(losers_matches) - 1,
        2,
    ):
        current_round = losers_matches[
            losers_round_index
        ]
        next_round = losers_matches[
            losers_round_index + 1
        ]

        for match_index, match in enumerate(
            current_round
        ):
            if match_index < len(next_round):
                match.winner_next_match_id = (
                    next_round[match_index].id
                )

    # Losers of later winners rounds drop into
    # the appropriate losers-bracket round.
    for winners_round_index in range(
        1,
        len(winners_matches),
    ):
        losers_target_index = (
            (winners_round_index * 2) - 1
        )

        if losers_target_index >= len(losers_matches):
            continue

        target_round = losers_matches[
            losers_target_index
        ]

        for match_index, match in enumerate(
            winners_matches[winners_round_index]
        ):
            if match_index < len(target_round):
                match.loser_next_match_id = (
                    target_round[match_index].id
                )

    # Final losers-bracket winner goes to
    # the grand final.
    if losers_matches and final_matches:
        final_losers_round = losers_matches[-1]

        for match in final_losers_round:
            match.winner_next_match_id = (
                final_matches[0].id
            )

    # Winners-bracket champion goes to
    # the grand final.
    if winners_matches and final_matches:
        winners_final = winners_matches[-1][0]

        winners_final.winner_next_match_id = (
            final_matches[0].id
        )

    db.commit()

    all_rounds = (
        winners_rounds
        + losers_rounds
        + final_rounds
    )

    for tournament_round in all_rounds:
        db.refresh(tournament_round)

    return all_rounds