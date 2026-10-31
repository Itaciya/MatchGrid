from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.data_access.database import get_db
from app.modules.tournament.schemas.tournament import (
    TournamentCreate,
    TournamentResponse,
    TournamentStandingResponse,
)
from app.modules.tournament.services.standings_service import (
    calculate_tournament_standings,
)
from app.modules.tournament.services.tournament_service import (
    create_tournament,
    get_tournament_by_id,
    list_tournaments,
)
from app.modules.user.models import User


router = APIRouter(
    prefix="/tournaments",
    tags=["Tournament"],
)


def _require_published_tournament(
    db: Session,
    tournament_id: int,
):
    """Ensure public endpoints expose only published tournaments."""

    tournament = get_tournament_by_id(
        db,
        tournament_id,
    )

    if (
        tournament is None
        or not tournament.fixtures_published
        or tournament.status == "archived"
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public tournament not found",
        )

    return tournament


@router.get(
    "/",
    response_model=list[TournamentResponse],
)
def get_tournaments(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return list_tournaments(
        db,
        status=status,
    )


@router.post(
    "/",
    response_model=TournamentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tournament_endpoint(
    data: TournamentCreate,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    """Create a tournament as an authorized organizer."""

    return create_tournament(
        db=db,
        organizer_id=current_user.id,
        data=data,
    )


@router.get(
    "/{tournament_id}",
    response_model=TournamentResponse,
)
def get_tournament_details(
    tournament_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    tournament = get_tournament_by_id(
        db,
        tournament_id,
    )

    if tournament is None or tournament.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tournament not found",
        )

    return tournament


@router.get("/{tournament_id}/image")
def get_tournament_image(
    tournament_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    """Return the uploaded image of a non-archived tournament."""

    tournament = get_tournament_by_id(
        db,
        tournament_id,
    )

    if (
        tournament is None
        or tournament.status == "archived"
        or tournament.image_data is None
        or tournament.image_content_type is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tournament image not found.",
        )

    return Response(
        content=tournament.image_data,
        media_type=tournament.image_content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get(
    "/{tournament_id}/standings",
    response_model=list[TournamentStandingResponse],
    status_code=status.HTTP_200_OK,
)
def get_tournament_standings_endpoint(
    tournament_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    """Return public standings based on verified official results."""

    _require_published_tournament(
        db,
        tournament_id,
    )

    return calculate_tournament_standings(
        db=db,
        tournament_id=tournament_id,
    )


@router.get(
    "/{tournament_id}/leaderboard",
    response_model=list[TournamentStandingResponse],
    status_code=status.HTTP_200_OK,
)
def get_public_tournament_leaderboard(
    tournament_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    """Return public team rankings without requiring authentication."""

    _require_published_tournament(
        db,
        tournament_id,
    )

    return calculate_tournament_standings(
        db=db,
        tournament_id=tournament_id,
    )
