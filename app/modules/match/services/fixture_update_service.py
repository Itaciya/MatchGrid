from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.match.schemas.fixture import FixtureUpdate
from app.modules.match.services.scheduling_conflict_service import (
    validate_schedule_conflicts,
)
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.tournament.models.tournament import Tournament
from app.modules.venue.models.venue import Venue


MATCH_DURATION = timedelta(hours=1)


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _validate_team_eligibility(
    db: Session,
    tournament_id: int,
    team_id: int,
) -> Team:
    """Require an active team with an approved tournament registration."""
    team = db.query(Team).filter(Team.id == team_id).first()

    if team is None:
        raise NotFoundException(
            detail=f"Team {team_id} not found"
        )

    if team.status != TeamStatus.ACTIVE:
        raise BadRequestException(
            detail=f"Team {team_id} is not active"
        )

    approved_registration = (
        db.query(Registration)
        .filter(
            Registration.tournament_id == tournament_id,
            Registration.team_id == team_id,
            Registration.registration_type == "team",
            Registration.status == "approved",
        )
        .first()
    )

    if approved_registration is None:
        raise BadRequestException(
            detail=(
                f"Team {team_id} does not have an approved "
                "registration for this tournament"
            )
        )

    return team


def update_fixture_schedule(
    db: Session,
    tournament_id: int,
    match_id: int,
    data: FixtureUpdate,
) -> Match:
    """Update fixture schedule, venue, or teams after validation."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    match = (
        db.query(Match)
        .filter(
            Match.id == match_id,
            Match.tournament_id == tournament_id,
        )
        .first()
    )

    if match is None:
        raise NotFoundException(
            detail="Fixture not found in this tournament"
        )

    if match.status != "scheduled":
        raise BadRequestException(
            detail="Only scheduled fixtures can be updated"
        )

    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise BadRequestException(
            detail="At least one field must be provided"
        )

    original_scheduled_at = match.scheduled_at
    original_venue_id = match.venue_id
    original_team_a_id = match.team_a_id
    original_team_b_id = match.team_b_id

    try:
        # SCRUM-126: Validate and update match date/time.
        if "scheduled_at" in changes:
            new_time = changes["scheduled_at"]

            if new_time.tzinfo is None:
                raise BadRequestException(
                    detail="scheduled_at must include a timezone"
                )

            new_time_utc = _as_utc(new_time)
            tournament_start = _as_utc(tournament.start_date)
            tournament_end = _as_utc(tournament.end_date)

            if (
                new_time_utc < tournament_start
                or new_time_utc + MATCH_DURATION > tournament_end
            ):
                raise BadRequestException(
                    detail=(
                        "Fixture must fit within the tournament date range"
                    )
                )

            match.scheduled_at = new_time_utc

        # SCRUM-127: Validate and update venue.
        if "venue_id" in changes:
            new_venue_id = changes["venue_id"]

            if new_venue_id is not None:
                venue = (
                    db.query(Venue)
                    .filter(Venue.id == new_venue_id)
                    .first()
                )

                if venue is None:
                    raise NotFoundException(
                        detail="Venue not found"
                    )

            match.venue_id = new_venue_id

        # SCRUM-128: Validate and update team A.
        if "team_a_id" in changes:
            new_team_a_id = changes["team_a_id"]

            if new_team_a_id is not None:
                _validate_team_eligibility(
                    db,
                    tournament_id,
                    new_team_a_id,
                )

            match.team_a_id = new_team_a_id

        # SCRUM-128: Validate and update team B.
        if "team_b_id" in changes:
            new_team_b_id = changes["team_b_id"]

            if new_team_b_id is not None:
                _validate_team_eligibility(
                    db,
                    tournament_id,
                    new_team_b_id,
                )

            match.team_b_id = new_team_b_id

        # Prevent the same team from occupying both positions.
        if (
            match.team_a_id is not None
            and match.team_a_id == match.team_b_id
        ):
            raise BadRequestException(
                detail="A team cannot occupy both fixture positions"
            )

        # Check conflicts against all scheduled matches.
        # The validator excludes the candidate match itself.
        scheduled_matches = (
            db.query(Match)
            .filter(Match.status == "scheduled")
            .all()
        )

        conflicts = validate_schedule_conflicts(
            candidate_matches=[match],
            existing_matches=scheduled_matches,
        )

        if conflicts:
            raise ConflictException(
                detail={
                    "message": (
                        "Fixture update rejected because schedule "
                        "conflicts exist"
                    ),
                    "conflicts": conflicts,
                }
            )

        changed = (
            _as_utc(match.scheduled_at)
            != _as_utc(original_scheduled_at)
            or match.venue_id != original_venue_id
            or match.team_a_id != original_team_a_id
            or match.team_b_id != original_team_b_id
        )

        # Keep bracket progression links intact.
        # Only unpublish fixtures if their actual details changed.
        if changed and tournament.fixtures_published:
            tournament.fixtures_published = False

        db.commit()
        db.refresh(match)

        return match

    except Exception:
        db.rollback()
        raise