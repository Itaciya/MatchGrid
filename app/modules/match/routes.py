from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import verify_tournament_owner
from app.core.exceptions import BadRequestException
from app.data_access.database import get_db

from app.modules.match.schemas.fixture import (
    FixtureCreate,
    FixtureResponse,
)

from app.modules.match.services.fixture_service import (
    create_round_robin_fixtures,
)

from app.modules.match.services.fixture_regeneration_service import (
    regenerate_round_robin_fixtures,
)

from app.modules.tournament.models.tournament import Tournament


router = APIRouter(
    prefix="/matches",
    tags=["Match"],
)


@router.post(
    "/tournaments/{tournament_id}/fixtures/generate",
    response_model=list[FixtureResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_fixtures_endpoint(
    tournament_id: int,
    data: FixtureCreate,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    """Generate fixtures for a tournament."""

    if data.tournament_id != tournament_id:
        raise BadRequestException(
            detail="Tournament ID in request body does not match path"
        )

    return create_round_robin_fixtures(
        db=db,
        tournament_id=tournament.id,
        team_ids=data.team_ids,
        fixture_date=data.fixture_date,
        fixture_time=data.fixture_time,
        venue_id=data.venue_id,
    )


@router.post(
    "/tournaments/{tournament_id}/fixtures/regenerate",
    response_model=list[FixtureResponse],
    status_code=status.HTTP_200_OK,
)
def regenerate_fixtures_endpoint(
    tournament_id: int,
    data: FixtureCreate,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    """Regenerate fixtures for a tournament."""

    if data.tournament_id != tournament_id:
        raise BadRequestException(
            detail="Tournament ID in request body does not match path"
        )

    return regenerate_round_robin_fixtures(
    db=db,
    tournament_id=tournament.id,
    team_ids=data.team_ids,
    fixture_date=data.fixture_date,
    fixture_time=data.fixture_time,
    venue_id=data.venue_id,
)