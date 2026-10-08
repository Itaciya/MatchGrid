from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.venue.models.venue import Venue
from app.modules.venue.schemas.venue import (
    VenueCreate,
    VenueUpdate,
)


def create_venue(
    db: Session,
    data: VenueCreate,
) -> Venue:
    """Create a new venue."""

    existing_venue = (
        db.query(Venue)
        .filter(Venue.name == data.name)
        .first()
    )

    if existing_venue:
        raise ConflictException(
            detail="A venue with this name already exists"
        )

    venue = Venue(
        name=data.name,
        location=data.location,
        description=data.description,
        capacity=data.capacity,
    )

    db.add(venue)
    db.commit()
    db.refresh(venue)

    return venue


def get_venues(
    db: Session,
) -> list[Venue]:
    """Return all venues."""

    return (
        db.query(Venue)
        .order_by(Venue.name)
        .all()
    )


def get_venue(
    db: Session,
    venue_id: int,
) -> Venue:
    """Return a venue by ID."""

    venue = (
        db.query(Venue)
        .filter(Venue.id == venue_id)
        .first()
    )

    if venue is None:
        raise NotFoundException(
            detail="Venue not found"
        )

    return venue


def update_venue(
    db: Session,
    venue_id: int,
    data: VenueUpdate,
) -> Venue:
    """Update an existing venue."""

    venue = get_venue(
        db=db,
        venue_id=venue_id,
    )

    if data.name is not None:
        existing_venue = (
            db.query(Venue)
            .filter(
                Venue.name == data.name,
                Venue.id != venue_id,
            )
            .first()
        )

        if existing_venue:
            raise ConflictException(
                detail="A venue with this name already exists"
            )

        venue.name = data.name

    if data.location is not None:
        venue.location = data.location

    if data.description is not None:
        venue.description = data.description

    if data.capacity is not None:
        venue.capacity = data.capacity

    db.commit()
    db.refresh(venue)

    return venue


def delete_venue(
    db: Session,
    venue_id: int,
) -> None:
    """Delete a venue if it has no assigned matches."""

    venue = get_venue(
        db=db,
        venue_id=venue_id,
    )

    assigned_match = (
        db.query(Match)
        .filter(Match.venue_id == venue_id)
        .first()
    )

    if assigned_match:
        raise BadRequestException(
            detail=(
                "Cannot delete a venue that is "
                "assigned to a match"
            )
        )

    db.delete(venue)
    db.commit()


def check_venue_availability(
    db: Session,
    venue_id: int,
    scheduled_at,
) -> bool:
    """Check whether a venue is available at a given time."""

    venue = get_venue(
        db=db,
        venue_id=venue_id,
    )

    existing_match = (
        db.query(Match)
        .filter(
            Match.venue_id == venue.id,
            Match.scheduled_at == scheduled_at,
            Match.status == "scheduled",
        )
        .first()
    )

    return existing_match is None