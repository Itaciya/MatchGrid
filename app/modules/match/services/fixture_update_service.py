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
from app.modules.tournament.models.tournament import Tournament
from app.modules.venue.models.venue import Venue


MATCH_DURATION = timedelta(hours=1)


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def update_fixture_schedule(
    db: Session,
    tournament_id: int,
    match_id: int,
    data: FixtureUpdate,
) -> Match:
    """Update a fixture after validating its schedule and venue."""

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

    try:
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

        scheduled_matches = (
            db.query(Match)
            .filter(
                Match.tournament_id == tournament_id,
                Match.status == "scheduled",
            )
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
        )

        if changed and tournament.fixtures_published:
            tournament.fixtures_published = False

        db.commit()
        db.refresh(match)

        return match

    except Exception:
        db.rollback()
        raise