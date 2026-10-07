from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.match.models.match import Match
from app.modules.match.services.match_validation import validate_teams_for_fixture
from app.modules.tournament.models.tournament import Tournament


def generate_round_robin_rounds(
    participant_ids: list[int],
) -> list[list[tuple[int, int]]]:
    """Generate round-robin rounds without overlapping participants."""

    if len(participant_ids) < 2:
        raise ValueError(
            "At least 2 participants are required"
        )

    participants = list(dict.fromkeys(participant_ids))

    if len(participants) != len(participant_ids):
        raise ValueError(
            "Duplicate participants are not allowed"
        )

    if len(participants) % 2 != 0:
        participants.append(None)

    rounds: list[list[tuple[int, int]]] = []
    total = len(participants)

    for _ in range(total - 1):
        current_round: list[tuple[int, int]] = []

        for index in range(total // 2):
            first = participants[index]
            second = participants[total - 1 - index]

            if first is not None and second is not None:
                current_round.append((first, second))

        rounds.append(current_round)

        participants = [
            participants[0],
            participants[-1],
            *participants[1:-1],
        ]

    return rounds


def generate_round_robin_pairings(
    participant_ids: list[int],
) -> list[tuple[int, int]]:
    """Generate every unique round-robin pairing."""

    return [
        match
        for current_round in generate_round_robin_rounds(participant_ids)
        for match in current_round
    ]


def generate_round_robin_fixtures(
    participant_ids: list[int],
    fixture_date: date,
    fixture_time: time,
) -> list[dict]:
    """Generate fixture records for all round-robin pairings."""

    pairings = generate_round_robin_pairings(participant_ids)

    scheduled_at = datetime.combine(
        fixture_date,
        fixture_time,
    )

    return [
        {
            "team_a_id": team_a_id,
            "team_b_id": team_b_id,
            "scheduled_at": scheduled_at,
            "status": "scheduled",
        }
        for team_a_id, team_b_id in pairings
    ]


def create_round_robin_fixtures(
    db: Session,
    tournament_id: int,
    team_ids: list[int],
    fixture_date: date,
    fixture_time: time,
) -> list[Match]:
    """Validate a tournament and save generated fixtures to the database."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(
            detail="Tournament not found"
        )

    if tournament.format != "round_robin":
        raise BadRequestException(
            detail="Round-robin fixtures require a round_robin tournament"
        )

    try:
        teams = validate_teams_for_fixture(
            db,
            tournament_id,
            team_ids,
        )
    except ValueError as exc:
        raise BadRequestException(
            detail=str(exc)
        ) from exc

    participant_ids = [team.id for team in teams]

    fixture_data = generate_round_robin_fixtures(
        participant_ids,
        fixture_date,
        fixture_time,
    )

    matches = [
        Match(
            tournament_id=tournament_id,
            team_a_id=fixture["team_a_id"],
            team_b_id=fixture["team_b_id"],
            scheduled_at=fixture["scheduled_at"],
            status=fixture["status"],
        )
        for fixture in fixture_data
    ]

    db.add_all(matches)
    db.commit()

    for match in matches:
        db.refresh(match)

    return matches
