from sqlalchemy.orm import Session

from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import TournamentCreate, TournamentUpdate


def create_tournament(db: Session, organizer_id: int, data: TournamentCreate) -> Tournament:
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


def update_tournament(db: Session, tournament: Tournament, data: TournamentUpdate) -> Tournament:
    """Apply a partial update. Caller (route) is responsible for having already
    verified the requester owns this tournament."""
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(tournament, field, value)

    db.commit()
    db.refresh(tournament)
    return tournament
