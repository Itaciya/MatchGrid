from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
    require_role,
    verify_tournament_owner,
)
from app.data_access.database import get_db
from app.modules.official_assignment.schemas.official_assignment import (
    AssignedMatchResponse,
    OfficialAssignmentCreate,
    OfficialAssignmentResponse,
)
from app.modules.official_assignment.services.official_assignment_service import (
    assign_official,
    get_my_assigned_matches,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


router = APIRouter(
    prefix="/official-assignments",
    tags=["Official Assignments"],
)


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}",
    response_model=OfficialAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_official_assignment_endpoint(
    match_id: int,
    data: OfficialAssignmentCreate,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    """Assign a referee or scorer to a match owned by the organizer."""

    return assign_official(
        db=db,
        tournament_id=tournament.id,
        match_id=match_id,
        official_id=data.official_id,
        assignment_type=data.assignment_type,
    )


@router.get(
    "/my-matches",
    response_model=list[AssignedMatchResponse],
    status_code=status.HTTP_200_OK,
)
def get_my_assigned_matches_endpoint(
    current_user: User = Depends(
        require_role("scorer", "official")
    ),
    db: Session = Depends(get_db),
):
    """Retrieve active match assignments for the logged-in official."""

    return get_my_assigned_matches(
        db=db,
        official=current_user,
    )