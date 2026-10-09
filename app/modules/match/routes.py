from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import verify_tournament_owner
from app.core.exceptions import BadRequestException, ConflictException
from app.data_access.database import get_db

from app.modules.match.models.match import Match
from app.modules.match.schemas.fixture import (
    FixtureCreate,
    FixtureResponse,
    FixtureUpdate,
)
from app.modules.match.services.fixture_service import (
    create_round_robin_fixtures,
)
from app.modules.match.services.fixture_regeneration_service import (
    regenerate_round_robin_fixtures,
)
from app.modules.match.services.scheduling_conflict_service import (
    validate_schedule_conflicts,
)
from app.modules.match.services.fixture_conflict_resolution_service import (
    resolve_fixture_conflicts,
)
from app.modules.match.services.fixture_update_service import (
    update_fixture_schedule,
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


@router.post(
    "/tournaments/{tournament_id}/fixtures/publish",
    status_code=status.HTTP_200_OK,
)
def publish_fixtures_endpoint(
    tournament_id: int,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    """Validate and publish a tournament's fixtures."""

    fixtures = (
        db.query(Match)
        .filter(Match.tournament_id == tournament.id)
        .order_by(Match.scheduled_at, Match.match_number)
        .all()
    )

    if not fixtures:
        raise BadRequestException(
            detail="Cannot publish fixtures because none exist"
        )

    scheduled_fixtures = [
        fixture
        for fixture in fixtures
        if fixture.status == "scheduled"
    ]

    if not scheduled_fixtures:
        raise BadRequestException(
            detail="Cannot publish because no scheduled fixtures exist"
        )

    conflicts = validate_schedule_conflicts(
        candidate_matches=scheduled_fixtures,
    )

    if conflicts:
        raise ConflictException(
            detail={
                "message": "Cannot publish fixtures because conflicts exist",
                "conflicts": conflicts,
            }
        )

    tournament.fixtures_published = True

    try:
        db.commit()
        db.refresh(tournament)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Fixtures published successfully",
        "tournament_id": tournament.id,
        "fixtures_published": tournament.fixtures_published,
        "fixture_count": len(scheduled_fixtures),
    }


@router.post(
    "/tournaments/{tournament_id}/fixtures/resolve-conflicts",
    status_code=status.HTTP_200_OK,
)
def resolve_fixture_conflicts_endpoint(
    tournament_id: int,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    """Resolve fixture scheduling conflicts for a tournament."""

    return resolve_fixture_conflicts(
        db=db,
        tournament_id=tournament.id,
    )


@router.patch(
    "/tournaments/{tournament_id}/fixtures/{match_id}",
    response_model=FixtureResponse,
    status_code=status.HTTP_200_OK,
)
def update_fixture_endpoint(
    tournament_id: int,
    match_id: int,
    data: FixtureUpdate,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    """Update a fixture after validating scheduling conflicts."""

    return update_fixture_schedule(
        db=db,
        tournament_id=tournament.id,
        match_id=match_id,
        data=data,
    )