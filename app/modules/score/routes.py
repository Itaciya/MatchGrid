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
from app.modules.score.services.score_service import create_score, get_score, update_score
from app.modules.match.services.match_result_service import (
    correct_match_result,
    finalize_match_result,
)
from app.modules.score.schemas.match_result import MatchResultResponse
from app.modules.score.schemas.match_result_correction import MatchResultCorrectionRequest
from app.modules.match.models.match import Match
from app.realtime.connection_manager import manager
router = APIRouter(
    prefix="/matches",
    tags=["Score"],
)

async def broadcast_live_score_update(db: Session, match_id: int, score: ScoreResponse) -> None:
    """Broadcast a successfully saved score to clients subscribed to its match."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if match is None:
        return

    event = {
        "type": "live_score:update",
        "payload": {
            "match_id": match.id,
            "match_number": match.match_number,
            "status": match.status,
            "team_a": {
                "id": match.team_a_id,
                "name": match.team_a.name if match.team_a else None,
                "score": score.team_a_score,
            },
            "team_b": {
                "id": match.team_b_id,
                "name": match.team_b.name if match.team_b else None,
                "score": score.team_b_score,
            },
            "score": {
                "team_a_score": score.team_a_score,
                "team_b_score": score.team_b_score,
            },
            "updated_at": (
                score.updated_at.isoformat()
                if score.updated_at
                else None
            ),
        },
    }

    await manager.broadcast_to_match(match_id, event)


@router.post(
    "/{match_id}/score",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_assigned_official)],
)

@router.post(
    "/{match_id}/score",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_assigned_official)],
)
async def submit_score_endpoint(
    match_id: int,
    data: ScoreCreate,
    db: Session = Depends(get_db),
):
    """Submit a score and broadcast it after successful persistence."""
    if data.match_id != match_id:
        raise BadRequestException(
            detail="Match ID in request body does not match path"
        )

    score = create_score(db, match_id, data)
    await broadcast_live_score_update(db, match_id, score)

    return score

@router.patch(
    "/{match_id}/score",
    response_model=ScoreResponse,
    dependencies=[Depends(verify_assigned_official)],
)

@router.patch(
    "/{match_id}/score",
    response_model=ScoreResponse,
    dependencies=[Depends(verify_assigned_official)],
)
async def update_score_endpoint(
    match_id: int,
    data: ScoreUpdate,
    db: Session = Depends(get_db),
):
    """Update a score and broadcast it after successful persistence."""
    score = update_score(db, match_id, data)
    await broadcast_live_score_update(db, match_id, score)

    return score

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
async def finalize_result_endpoint(
    match_id: int,
    organiser: User = Depends(verify_match_organiser),
    db: Session = Depends(get_db),
):
    """Finalize a match result and broadcast its completed status."""

    result = finalize_match_result(db, match_id, organiser.id)

    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .first()
    )

    if match is not None:
        await manager.broadcast_to_match(
            match.id,
            {
                "type": "match_status:update",
                "payload": {
                    "match_id": match.id,
                    "status": match.status,
                },
            },
        )

    return result

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


@router.get(
    "/{match_id}/score",
    response_model=ScoreResponse,
    dependencies=[Depends(verify_assigned_official)],
)
def get_score_endpoint(
    match_id: int,
    db: Session = Depends(get_db),
):
    """Current score for a match. Assigned officials only."""
    return get_score(db, match_id)

@router.get(
    "/{match_id}/score/review",
    response_model=ScoreResponse,
    dependencies=[Depends(verify_match_organiser)],
)
def get_score_for_review_endpoint(
    match_id: int,
    db: Session = Depends(get_db),
):
    """Current score for review. Organiser of the match's tournament only."""
    return get_score(db, match_id)