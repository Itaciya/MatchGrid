from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import verify_assigned_official, verify_match_organiser
from app.core.exceptions import BadRequestException
from app.data_access.database import get_db
from app.modules.score.schemas.score import ScoreVerificationDecision
from app.modules.score.services.score_verification_service import review_score
from app.modules.user.models import User
from app.modules.score.schemas.score import (
    ScoreCreate,
    ScoreResponse,
    ScoreUpdate,
)
from app.modules.score.services.score_service import create_score, update_score
from app.modules.match.services.match_result_service import (
    correct_match_result,
    finalize_match_result,
)
from app.modules.score.schemas.match_result import MatchResultResponse
from app.modules.score.schemas.match_result_correction import MatchResultCorrectionRequest

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


@router.patch(
    "/{match_id}/score/verification",
    response_model=ScoreResponse,
)
def review_score_endpoint(
    match_id: int,
    data: ScoreVerificationDecision,
    organiser: User = Depends(verify_match_organiser),
    db: Session = Depends(get_db),
):
    """Verify or reject a submitted score. Organiser of the match's tournament only."""
    return review_score(db, match_id, organiser.id, data.status)


@router.post(
    "/{match_id}/result/finalize",
    response_model=MatchResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def finalize_result_endpoint(
    match_id: int,
    organiser: User = Depends(verify_match_organiser),
    db: Session = Depends(get_db),
):
    """Finalize a match result from its verified score. Organiser of the match's tournament only."""
    return finalize_match_result(db, match_id, organiser.id)


@router.patch(
    "/{match_id}/result",
    response_model=MatchResultResponse,
)
def correct_result_endpoint(
    match_id: int,
    data: MatchResultCorrectionRequest,
    organiser: User = Depends(verify_match_organiser),
    db: Session = Depends(get_db),
):
    """Correct a finalized result. Organiser of the match's tournament only;
    every correction is recorded in the audit trail."""
    return correct_match_result(
        db,
        match_id,
        organiser.id,
        data.team_a_score,
        data.team_b_score,
        data.reason,
    )
