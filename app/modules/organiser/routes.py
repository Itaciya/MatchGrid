from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role, verify_tournament_owner
from app.data_access.database import get_db
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import (
    TournamentCreate,
    TournamentResponse,
    TournamentUpdate,
)
from app.modules.tournament.services.tournament_service import (
    create_tournament,
    update_tournament,
)
from app.modules.user.models import User

router = APIRouter(
    prefix="/organiser",
    tags=["Organiser"],
)


@router.get("/")
def organiser_home():
    return {
        "message": "Organiser router is working"
    }


@router.post(
    "/tournaments",
    response_model=TournamentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tournament_route(
    data: TournamentCreate,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    return create_tournament(db, current_user.id, data)


@router.patch(
    "/tournaments/{tournament_id}",
    response_model=TournamentResponse,
)
def update_tournament_route(
    data: TournamentUpdate,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    return update_tournament(db, tournament, data)
