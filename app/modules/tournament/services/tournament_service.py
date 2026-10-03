from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import (
    TournamentCreate,
    TournamentUpdate,
)

TOURNAMENT_FORMATS = {
    "knockout",
    "round_robin",
    "league",
    "single_elimination",
}
TOURNAMENT_STATUSES = {
    "upcoming",
    "ongoing",
    "completed",
    "archived",
}


VALID_STATUS_TRANSITIONS = {
    "upcoming": {"ongoing"},
    "ongoing": {"completed"},
    "completed": {"archived"},
    "archived": set(),
}


# -------------------------------------------------------------------
# Tournament Creation
# -------------------------------------------------------------------

def create_tournament(
    db: Session,
    organizer_id: int,
    data: TournamentCreate,
) -> Tournament:
    """Create a new tournament with upcoming status."""
    validate_tournament_format(data.format)
    tournament = Tournament(
        name=data.name,
        description=data.description,
        format=data.format,
        start_date=data.start_date,
        end_date=data.end_date,
        status="upcoming",
        organizer_id=organizer_id,
    )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    return tournament


def update_tournament(
    db: Session,
    tournament: Tournament,
    data: TournamentUpdate,
) -> Tournament:
    """Apply a partial update to tournament details.

    Tournament status must be changed through the centralized
    status transition logic instead of a normal update.
    """

    updates = data.model_dump(exclude_unset=True)
    if "format" in updates:
      validate_tournament_format(updates["format"])
    # Status cannot be changed through normal tournament update.
    if "status" in updates:
        raise BadRequestException(
            detail="Tournament status cannot be changed through update"
        )

    new_start_date = updates.get(
        "start_date",
        tournament.start_date,
    )

    new_end_date = updates.get(
        "end_date",
        tournament.end_date,
    )

    if new_end_date <= new_start_date:
        raise BadRequestException(
            detail="end_date must be after start_date"
        )

    for field, value in updates.items():
        setattr(tournament, field, value)

    db.commit()
    db.refresh(tournament)

    return tournament

def validate_tournament_format(format: str) -> None:
    """Validate that a tournament format is supported."""

    if format not in TOURNAMENT_FORMATS:
        raise BadRequestException(
            detail=f"Invalid tournament format: {format}"
        )
def validate_tournament_status(status: str) -> None:
    """Validate that a tournament status is supported."""

    if status not in TOURNAMENT_STATUSES:
        raise BadRequestException(
            detail=f"Invalid tournament status: {status}"
        )


def can_transition_tournament_status(
    current_status: str,
    new_status: str,
) -> bool:
    """Return whether a status transition is allowed."""

    validate_tournament_status(current_status)
    validate_tournament_status(new_status)

    return new_status in VALID_STATUS_TRANSITIONS[current_status]


# -------------------------------------------------------------------
# Tournament Status Change
# -------------------------------------------------------------------

def change_tournament_status(
    db: Session,
    tournament: Tournament,
    new_status: str,
) -> Tournament:
    """Change tournament status using the centralized transition rules."""

    validate_tournament_status(new_status)

    current_status = tournament.status

    if not can_transition_tournament_status(
        current_status,
        new_status,
    ):
        raise BadRequestException(
            detail=(
                f"Invalid tournament status transition: "
                f"{current_status} -> {new_status}"
            )
        )

    tournament.status = new_status

    db.commit()
    db.refresh(tournament)

    return tournament


# -------------------------------------------------------------------
# Tournament Listing
# -------------------------------------------------------------------

def list_tournaments(
    db: Session,
    status: str | None = None,
) -> list[Tournament]:
    """Return tournaments, optionally filtered by status."""



    query = db.query(Tournament)

    if status is not None:
        query = query.filter(
            Tournament.status == status
        )

    return query.order_by(
        Tournament.start_date.asc()
    ).all()


# -------------------------------------------------------------------
# Get Tournament
# -------------------------------------------------------------------

def get_tournament_by_id(
    db: Session,
    tournament_id: int,
) -> Tournament | None:
    """Return a tournament by ID, or None if it does not exist."""

    return (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )


# -------------------------------------------------------------------
# Archive Tournament
# -------------------------------------------------------------------

def archive_tournament(
    db: Session,
    tournament: Tournament,
) -> Tournament:
    """Archive a completed tournament without deleting its history."""

    if tournament.status != "completed":
        raise BadRequestException(
            detail="Only completed tournaments can be archived"
        )

    return change_tournament_status(
        db,
        tournament,
        "archived",
    )
