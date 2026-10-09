
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.match.models.match import Match
from app.modules.match.services.scheduling_conflict_service import (
    validate_schedule_conflicts,
)
from app.modules.tournament.models.tournament import Tournament


MATCH_DURATION = timedelta(hours=1)


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime for schedule comparisons."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _get_candidate_slots(
    tournament: Tournament,
) -> list[datetime]:
    """Generate hourly slots within the tournament date range."""

    start = _as_utc(tournament.start_date)
    end = _as_utc(tournament.end_date)

    # Round the start time up to the next whole hour when needed.
    slot = start.replace(minute=0, second=0, microsecond=0)

    if slot < start:
        slot += MATCH_DURATION

    slots = []

    while slot + MATCH_DURATION <= end:
        slots.append(slot)
        slot += MATCH_DURATION

    return slots


def resolve_fixture_conflicts(
    db: Session,
    tournament_id: int,
) -> dict:
    """
    Attempt to resolve schedule conflicts by moving scheduled
    matches to alternative hourly slots.

    All changes are committed together only when the complete
    scheduled fixture list has no remaining conflicts.
    """

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament_id,
            Match.status == "scheduled",
        )
        .order_by(Match.scheduled_at, Match.match_number)
        .all()
    )

    if not matches:
        raise ConflictException(
            detail="No scheduled fixtures are available to resolve"
        )

    original_times = {
        match.id: match.scheduled_at
        for match in matches
    }

    candidate_slots = _get_candidate_slots(tournament)

    if not candidate_slots:
        raise ConflictException(
            detail="No valid time slots exist within the tournament dates"
        )

    try:
        conflicts = validate_schedule_conflicts(
            candidate_matches=matches,
        )

        # Each successful move removes at least one conflict
        # involving the moved match. The limit prevents endless retries.
        max_attempts = max(len(matches) * len(matches), 1)
        attempts = 0

        while conflicts and attempts < max_attempts:
            attempts += 1
            resolved_one = False

            involved_ids = []
            for conflict in conflicts:
                for match_id in conflict["match_ids"]:
                    if match_id not in involved_ids:
                        involved_ids.append(match_id)

            for match_id in involved_ids:
                match = next(
                    (
                        item
                        for item in matches
                        if item.id == match_id
                    ),
                    None,
                )

                if match is None or match.status != "scheduled":
                    continue

                original_time = match.scheduled_at

                for slot in candidate_slots:
                    if _as_utc(slot) == _as_utc(original_time):
                        continue

                    match.scheduled_at = slot

                    candidate_conflicts = validate_schedule_conflicts(
                        candidate_matches=[match],
                        existing_matches=matches,
                    )

                    if not candidate_conflicts:
                        conflicts = validate_schedule_conflicts(
                            candidate_matches=matches,
                        )
                        resolved_one = True
                        break

                if resolved_one:
                    break

                match.scheduled_at = original_time

            if not resolved_one:
                raise ConflictException(
                    detail={
                        "message": (
                            "Unable to resolve all fixture conflicts "
                            "within the tournament date range"
                        ),
                        "conflicts": conflicts,
                    }
                )

        if conflicts:
            raise ConflictException(
                detail={
                    "message": "Fixture conflicts remain unresolved",
                    "conflicts": conflicts,
                }
            )

        changed_matches = [
            match
            for match in matches
            if _as_utc(match.scheduled_at)
            != _as_utc(original_times[match.id])
        ]

        if changed_matches and tournament.fixtures_published:
            tournament.fixtures_published = False

        db.commit()

        return {
            "message": "Fixture conflicts resolved successfully",
            "tournament_id": tournament_id,
            "resolved_count": len(changed_matches),
            "fixtures_published": tournament.fixtures_published,
            "updated_matches": [
                {
                    "match_id": match.id,
                    "scheduled_at": match.scheduled_at,
                }
                for match in changed_matches
            ],
        }

    except Exception:
        db.rollback()
        raise