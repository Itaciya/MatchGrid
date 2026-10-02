from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import (
    TournamentCreate,
    TournamentUpdate,
)


def create_tournament(
    db: Session,
    organizer_id: int,
    data: TournamentCreate,
) -> Tournament:
    """Create a tournament owned by organizer_id (the authenticated user)."""
    tournament = Tournament(
        name=data.name,
        description=data.description,
        format=data.format,
        start_date=data.start_date,
        end_date=data.end_date,
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
    """Apply a partial update. Caller (route) is responsible for having already
    verified the requester owns this tournament."""
    updates = data.model_dump(exclude_unset=True)

    new_start_date = updates.get("start_date", tournament.start_date)
    new_end_date = updates.get("end_date", tournament.end_date)

    if new_end_date <= new_start_date:
        raise BadRequestException(
            detail="end_date must be after start_date"
        )

    for field, value in updates.items():
        setattr(tournament, field, value)

    db.commit()
    db.refresh(tournament)
    return tournament


def list_tournaments(
    db: Session,
    status: str | None = None,
) -> list[Tournament]:
    """Return tournaments, optionally filtered by status."""
    query = db.query(Tournament)

    if status is not None:
        query = query.filter(Tournament.status == status)

    return query.order_by(Tournament.start_date.asc()).all()


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
def archive_tournament(
    db: Session,
    tournament: Tournament,
) -> Tournament:
    """Archive a completed tournament without deleting its history."""
    if tournament.status != "completed":
        raise BadRequestException(
            detail="Only completed tournaments can be archived"
        )

    tournament.status = "archived"

    db.commit()
    db.refresh(tournament)

    return tournament
