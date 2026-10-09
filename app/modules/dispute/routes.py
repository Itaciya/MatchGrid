from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.data_access.database import get_db
from app.modules.dispute.schemas.dispute import (
    DisputeCreate,
    DisputeResponse,
    DisputeStatusUpdate,
    DisputeResolutionRequest,
    OrganizerDisputeReviewResponse,
)
from app.modules.dispute.services.dispute_service import (
    create_dispute,
    get_dispute_by_id,
    get_disputes_by_match,
    get_pending_disputes_for_organizer,
    update_dispute_status,
    resolve_dispute,
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
    "/pending",
    response_model=list[OrganizerDisputeReviewResponse],
    status_code=status.HTTP_200_OK,
)
def get_pending_disputes_for_organizer_endpoint(
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """List pending disputes for tournaments owned by the organiser."""
    disputes = get_pending_disputes_for_organizer(
        db=db,
        current_user_id=current_user.id,
    )

    return [
        {
            "id": dispute.id,
            "match_id": dispute.match_id,
            "user_id": dispute.user_id,
            "reason": dispute.reason,
            "status": dispute.status,
            "resolution": dispute.resolution,
            "created_at": dispute.created_at,
            "updated_at": dispute.updated_at,
            "match": {
                "id": dispute.match.id,
                "match_number": dispute.match.match_number,
                "scheduled_at": dispute.match.scheduled_at,
                "status": dispute.match.status,
                "team_a_id": dispute.match.team_a_id,
                "team_b_id": dispute.match.team_b_id,
                "team_a_name": dispute.match.team_a.name,
                "team_b_name": dispute.match.team_b.name,
            },
            "result": (
                {
                    "team_a_score": dispute.match.score.team_a_score,
                    "team_b_score": dispute.match.score.team_b_score,
                    "verification_status": (
                        dispute.match.score.verification_status
                    ),
                }
                if dispute.match.score is not None
                else None
            ),
        }
        for dispute in disputes
    ]


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


@router.patch(
    "/{dispute_id}/resolve",
    response_model=DisputeResponse,
    status_code=status.HTTP_200_OK,
)
def resolve_dispute_endpoint(
    dispute_id: int,
    data: DisputeResolutionRequest,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Resolve or reject a dispute as its tournament's organiser."""
    return resolve_dispute(
        db=db,
        current_user_id=current_user.id,
        dispute_id=dispute_id,
        data=data,
    )


@router.patch(
    "/{dispute_id}/status",
    response_model=DisputeResponse,
    status_code=status.HTTP_200_OK,
)
def update_dispute_status_endpoint(
    dispute_id: int,
    data: DisputeStatusUpdate,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Update dispute status for a tournament owned by the organiser."""
    return update_dispute_status(
        db=db,
        current_user_id=current_user.id,
        dispute_id=dispute_id,
        data=data,
    )