
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
from app.modules.notification.models.notification import Notification
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament


MATCH_DURATION = timedelta(hours=1)
MATCH_STATUS_SCHEDULED = "scheduled"
FIXTURE_PUBLISHED_NOTIFICATION = "fixture_published"


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC for reliable comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _create_fixture_publication_notifications(
    db: Session,
    tournament: Tournament,
    fixtures: list[Match],
) -> None:
    """Add publication notifications for participating team captains."""

    team_ids = {
        team_id
        for fixture in fixtures
        for team_id in (fixture.team_a_id, fixture.team_b_id)
        if team_id is not None
    }

    if not team_ids:
        return

    teams = (
        db.query(Team)
        .filter(Team.id.in_(team_ids))
        .all()
    )

    recipient_ids = {
        team.captain_id
        for team in teams
        if team.captain_id is not None
    }

    fixture_details = []

    for fixture in fixtures:
        team_a = next(
            (
                team.name
                for team in teams
                if team.id == fixture.team_a_id
            ),
            f"Team {fixture.team_a_id}",
        )

        team_b = next(
            (
                team.name
                for team in teams
                if team.id == fixture.team_b_id
            ),
            f"Team {fixture.team_b_id}",
        )

        scheduled_at = _as_utc(fixture.scheduled_at).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

        fixture_details.append(
            f"Match {fixture.match_number}: "
            f"{team_a} vs {team_b}, scheduled at {scheduled_at}"
        )

    message = (
        f"Fixtures have been published for tournament "
        f"'{tournament.name}'. "
        f"Total fixtures: {len(fixtures)}. "
        + " | ".join(fixture_details)
    )

    for recipient_id in recipient_ids:
        existing_notification = (
            db.query(Notification)
            .filter(
                Notification.user_id == recipient_id,
                Notification.notification_type
                == FIXTURE_PUBLISHED_NOTIFICATION,
                Notification.content == message,
            )
            .first()
        )

        if existing_notification is not None:
            continue

        db.add(
            Notification(
                user_id=recipient_id,
                notification_type=FIXTURE_PUBLISHED_NOTIFICATION,
                content=message,
                is_read=False,
            )
        )


def publish_fixtures(
    db: Session,
    tournament: Tournament,
) -> dict:
    """Validate and publish fixtures for an authorized tournament."""

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

    if tournament.fixtures_published:
        return {
            "message": "Fixtures have already been published",
            "tournament_id": tournament.id,
            "fixtures_published": True,
            "fixture_count": len(scheduled_fixtures),
        }

    tournament.fixtures_published = True

    try:
        _create_fixture_publication_notifications(
            db=db,
            tournament=tournament,
            fixtures=scheduled_fixtures,
        )

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
