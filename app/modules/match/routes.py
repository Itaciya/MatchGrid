from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    verify_assigned_official,
    verify_tournament_owner,
)
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.data_access.database import get_db

from app.modules.match.models.match import Match
from app.modules.match.schemas.fixture import (
    FixtureCreate,
    FixtureResponse,
    FixtureUpdate,
)
from app.modules.match.schemas.match import MatchStatusResponse
from app.modules.match.services.fixture_service import (
    create_round_robin_fixtures,
)
from app.modules.match.services.fixture_regeneration_service import (
    regenerate_round_robin_fixtures,
)
from app.modules.match.services.fixture_conflict_resolution_service import (
    resolve_fixture_conflicts,
)
from app.modules.match.services.fixture_update_service import (
    update_fixture_schedule,
)
from app.modules.match.services.fixture_publication_service import (
    publish_fixtures,
)
from app.modules.match.services.match_start_service import start_match
from app.modules.tournament.models.tournament import Tournament
from app.modules.match.services.match_status_service import complete_match

router = APIRouter(
    prefix="/matches",
    tags=["Match"],
)


# SCRUM-123: List fixtures with optional filters
@router.get(
    "/tournaments/{tournament_id}/fixtures",
    response_model=list[FixtureResponse],
    status_code=status.HTTP_200_OK,
)
def list_fixtures_endpoint(
    tournament_id: int,
    fixture_status: str | None = Query(default=None, alias="status"),
    team_id: int | None = Query(default=None, gt=0),
    venue_id: int | None = Query(default=None, gt=0),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """List tournament fixtures with optional filters."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    if start_at and end_at and start_at > end_at:
        raise BadRequestException(
            detail="start_at must be before or equal to end_at"
        )

    query = db.query(Match).filter(
        Match.tournament_id == tournament_id
    )

    if fixture_status:
        query = query.filter(Match.status == fixture_status)

    if team_id is not None:
        query = query.filter(
            (Match.team_a_id == team_id)
            | (Match.team_b_id == team_id)
        )

    if venue_id is not None:
        query = query.filter(Match.venue_id == venue_id)

    if start_at is not None:
        query = query.filter(Match.scheduled_at >= start_at)

    if end_at is not None:
        query = query.filter(Match.scheduled_at <= end_at)

    return query.order_by(
        Match.scheduled_at,
        Match.match_number,
    ).all()


# SCRUM-124: Get fixture details by ID
@router.get(
    "/tournaments/{tournament_id}/fixtures/{match_id}",
    response_model=FixtureResponse,
    status_code=status.HTTP_200_OK,
)
def get_fixture_details_endpoint(
    tournament_id: int,
    match_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve fixture details for a tournament."""

    fixture = (
        db.query(Match)
        .filter(
            Match.id == match_id,
            Match.tournament_id == tournament_id,
        )
        .first()
    )

    if fixture is None:
        raise NotFoundException(detail="Fixture not found")

    return fixture


# Generate fixtures
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


# Regenerate fixtures
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


# SCRUM-130: Publish fixtures after validation
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

    return publish_fixtures(
        db=db,
        tournament=tournament,
    )


# Resolve fixture scheduling conflicts
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


# SCRUM-125: Update fixture schedule or venue
# SCRUM-131: Organizer authorization is enforced by the dependency.
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


# Start a match
@router.post(
    "/{match_id}/start",
    response_model=MatchStatusResponse,
    dependencies=[Depends(verify_assigned_official)],
)
def start_match_endpoint(
    match_id: int,
    db: Session = Depends(get_db),
):
    """Start a scheduled match and record server time."""

    return start_match(db, match_id)

@router.post(
    "/{match_id}/complete",
    response_model=MatchStatusResponse,
    dependencies=[Depends(verify_assigned_official)],
)
def complete_match_endpoint(
    match_id: int,
    db: Session = Depends(get_db),
):
    """Complete a live match by an assigned official."""

    return complete_match(db, match_id)