from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import verify_assigned_official
from app.core.exceptions import BadRequestException
from app.data_access.database import get_db
from app.modules.score.schemas.score import (
    ScoreCreate,
    ScoreResponse,
    ScoreUpdate,
)
from app.modules.score.services.score_service import create_score, update_score

router = APIRouter(
    prefix="/matches",
    tags=["Score"],
)


@router.post(
    "/{match_id}/score",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_assigned_official)],
)
def submit_score_endpoint(
    match_id: int,
    data: ScoreCreate,
    db: Session = Depends(get_db),
):
    """Submit a live score. Assigned officials only."""
    if data.match_id != match_id:
        raise BadRequestException(
            detail="Match ID in request body does not match path"
        )

    return create_score(db, match_id, data)


@router.patch(
    "/{match_id}/score",
    response_model=ScoreResponse,
    dependencies=[Depends(verify_assigned_official)],
)
def update_score_endpoint(
    match_id: int,
    data: ScoreUpdate,
    db: Session = Depends(get_db),
):
    """Update a live score. Assigned officials only; finalized scores are locked."""
    return update_score(db, match_id, data)
