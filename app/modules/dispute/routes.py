from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.data_access.database import get_db
from app.modules.dispute.schemas.dispute import (
    DisputeCreate,
    DisputeResponse,
)
from app.modules.dispute.services.dispute_service import create_dispute
from app.modules.user.models import User


router = APIRouter(
    prefix="/disputes",
    tags=["Dispute"],
)


@router.post(
    "/",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dispute_endpoint(
    data: DisputeCreate,
    current_user: User = Depends(require_role("player")),
    db: Session = Depends(get_db),
):
    """Submit a dispute for a match the authenticated player participates in."""
    return create_dispute(
        db=db,
        current_user_id=current_user.id,
        data=data,
    )