from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.data_access.database import get_db
from app.modules.tournament.schemas.tournament import TournamentResponse
from app.modules.tournament.services.tournament_service import list_tournaments


router = APIRouter(
    prefix="/tournaments",
    tags=["Tournament"],
)


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