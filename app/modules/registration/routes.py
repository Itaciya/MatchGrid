from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.data_access.database import get_db
from app.modules.registration.schemas.registration import (
    RegistrationCreate,
    RegistrationResponse,
)
from app.modules.registration.services.registration_service import (
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
def create_registration(
    data: RegistrationCreate,
    current_user: User = Depends(require_role("captain")),
    db: Session = Depends(get_db),
):
    return create_team_registration(
        db,
        current_user.id,
        data,
    )
