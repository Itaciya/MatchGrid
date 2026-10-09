from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
)
from app.modules.match.models.match import Match
from app.modules.match.services.scheduling_conflict_service import (
    validate_schedule_conflicts,
)
from app.modules.tournament.models.tournament import Tournament


MATCH_DURATION = timedelta(hours=1)
MATCH_STATUS_SCHEDULED = "scheduled"


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC for reliable comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def publish_fixtures(
    db: Session,
    tournament: Tournament,
) -> dict:
    """Validate and publish fixtures for an authorized tournament.

    Organizer ownership is checked by the route dependency.
    Fixtures are published only when they are complete and conflict-free.
    """

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
        if fixture.status == MATCH_STATUS_SCHEDULED
    ]

    if not scheduled_fixtures:
        raise BadRequestException(
            detail="Cannot publish because no scheduled fixtures exist"
        )

    tournament_start = _as_utc(tournament.start_date)
    tournament_end = _as_utc(tournament.end_date)

    # Validate completeness and schedule boundaries before publication.
    for fixture in scheduled_fixtures:
        if fixture.team_a_id is None or fixture.team_b_id is None:
            raise BadRequestException(
                detail=(
                    f"Fixture {fixture.match_number} is incomplete: "
                    "both teams must be assigned before publication"
                )
            )

        if fixture.team_a_id == fixture.team_b_id:
            raise BadRequestException(
                detail=(
                    f"Fixture {fixture.match_number} is invalid: "
                    "both teams cannot be the same"
                )
            )

        scheduled_at = _as_utc(fixture.scheduled_at)

        if (
            scheduled_at < tournament_start
            or scheduled_at + MATCH_DURATION > tournament_end
        ):
            raise BadRequestException(
                detail=(
                    f"Fixture {fixture.match_number} falls outside "
                    "the tournament date range"
                )
            )

    # Reject conflicts before changing the publication flag.
    conflicts = validate_schedule_conflicts(
        candidate_matches=scheduled_fixtures,
    )

    if conflicts:
        raise ConflictException(
            detail={
                "message": (
                    "Cannot publish fixtures because conflicts exist"
                ),
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