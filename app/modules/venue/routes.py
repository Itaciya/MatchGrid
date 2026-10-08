from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.data_access.database import get_db
from app.modules.user.models import User
from app.modules.venue.schemas.venue import (
    VenueCreate,
    VenueResponse,
    VenueUpdate,
)
from app.modules.venue.services.venue_service import (
    create_venue,
    delete_venue,
    get_venue,
    get_venues,
    update_venue,
)


router = APIRouter(
    prefix="/venues",
    tags=["Venue"],
)


@router.post(
    "/",
    response_model=VenueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_venue_endpoint(
    data: VenueCreate,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Create a new venue."""

    return create_venue(
        db,
        data,
    )


@router.get(
    "/",
    response_model=list[VenueResponse],
    status_code=status.HTTP_200_OK,
)
def get_venues_endpoint(
    db: Session = Depends(get_db),
):
    """Get all venues."""

    return get_venues(db)


@router.get(
    "/{venue_id}",
    response_model=VenueResponse,
    status_code=status.HTTP_200_OK,
)
def get_venue_endpoint(
    venue_id: int,
    db: Session = Depends(get_db),
):
    """Get venue details."""

    return get_venue(
        db,
        venue_id,
    )


@router.patch(
    "/{venue_id}",
    response_model=VenueResponse,
    status_code=status.HTTP_200_OK,
)
def update_venue_endpoint(
    venue_id: int,
    data: VenueUpdate,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Update venue information."""

    return update_venue(
        db,
        venue_id,
        data,
    )


@router.delete(
    "/{venue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_venue_endpoint(
    venue_id: int,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Delete a venue."""

    delete_venue(
        db,
        venue_id,
    )

    return None