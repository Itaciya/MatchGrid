
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.data_access.database import get_db
from app.modules.dispute.schemas.dispute import (
    DisputeCreate,
    DisputeResponse,
)
from app.modules.dispute.services.dispute_service import (
    create_dispute,
    get_dispute_by_id,
    get_disputes_by_match,
)
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


@router.get(
    "/match/{match_id}",
    response_model=list[DisputeResponse],
    status_code=status.HTTP_200_OK,
)
def get_disputes_by_match_endpoint(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve disputes for a match the current user may access."""
    return get_disputes_by_match(
        db=db,
        current_user_id=current_user.id,
        match_id=match_id,
    )


@router.get(
    "/{dispute_id}",
    response_model=DisputeResponse,
    status_code=status.HTTP_200_OK,
)
def get_dispute_by_id_endpoint(
    dispute_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a dispute the current user may access."""
    return get_dispute_by_id(
        db=db,
        current_user_id=current_user.id,
        dispute_id=dispute_id,
    )
