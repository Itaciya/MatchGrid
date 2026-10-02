from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.data_access.database import get_db
from app.modules.registration.schemas.registration import (
    RegistrationCreate,
    RegistrationResponse,
)
from app.modules.registration.services.registration_service import (
    create_player_registration,
    create_team_registration,
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
