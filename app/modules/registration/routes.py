from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.data_access.database import get_db
from app.modules.registration.schemas.registration import (
    RegistrationCreate,
    RegistrationResponse,
    RegistrationStatus,
)
from app.modules.registration.services.registration_service import (
    approve_registration,
    create_player_registration,
    create_team_registration,
    get_pending_registrations,
    reject_registration,
    update_registration_status,
)
from app.modules.user.models import User


router = APIRouter(
    prefix="/registrations",
    tags=["Registration"],
)


@router.post(
    "/",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_team_registration_endpoint(
    data: RegistrationCreate,
    current_user: User = Depends(require_role("captain")),
    db: Session = Depends(get_db),
):
    """Register a team for a tournament."""
    return create_team_registration(
        db,
        current_user.id,
        data,
    )


@router.post(
    "/player",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_player_registration_endpoint(
    data: RegistrationCreate,
    current_user: User = Depends(require_role("player")),
    db: Session = Depends(get_db),
):
    """Register the authenticated player for a tournament."""
    return create_player_registration(
        db,
        current_user.id,
        data,
    )


@router.get(
    "/pending/{tournament_id}",
    response_model=list[RegistrationResponse],
    status_code=status.HTTP_200_OK,
)
def get_pending_registrations_endpoint(
    tournament_id: int,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Retrieve pending registrations for a tournament."""
    return get_pending_registrations(
        db,
        tournament_id,
    )


@router.patch(
    "/{registration_id}/approve",
    response_model=RegistrationResponse,
    status_code=status.HTTP_200_OK,
)
def approve_registration_endpoint(
    registration_id: int,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Approve a pending registration."""
    return approve_registration(
        db,
        registration_id,
    )


@router.patch(
    "/{registration_id}/reject",
    response_model=RegistrationResponse,
    status_code=status.HTTP_200_OK,
)
def reject_registration_endpoint(
    registration_id: int,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Reject a pending registration."""
    return reject_registration(
        db,
        registration_id,
    )


@router.patch(
    "/{registration_id}/status",
    response_model=RegistrationResponse,
    status_code=status.HTTP_200_OK,
)
def update_registration_status_endpoint(
    registration_id: int,
    new_status: RegistrationStatus,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Update registration status by an organizer."""
    return update_registration_status(
        db,
        registration_id,
        new_status,
    )
