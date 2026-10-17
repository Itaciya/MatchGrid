
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.modules.match.models.match import Match
from app.modules.notification.models.notification import Notification
from app.modules.player_team.models.player import Player
from app.modules.registration.models.registration import Registration
from app.modules.player_team.models.team import Team


REMINDER_NOTIFICATION_TYPE = "upcoming_match_reminder"


def generate_upcoming_match_reminders(
    db: Session,
    now: datetime | None = None,
    reminder_minutes: int = 60,
    window_minutes: int = 1,
) -> int:
    """
    Create reminders for scheduled matches approaching their reminder time.

    The time window allows a scheduler running periodically to find matches
    whose reminder time has just arrived.

    Returns the number of notifications created.
    """
    if reminder_minutes <= 0:
        raise ValueError("reminder_minutes must be greater than zero")

    if window_minutes <= 0:
        raise ValueError("window_minutes must be greater than zero")

    if now is None:
        now = datetime.now(timezone.utc)

    reminder_start = now + timedelta(
    minutes=reminder_minutes - window_minutes
)
    reminder_end = now + timedelta(minutes=reminder_minutes)

    matches = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.scheduled_at > reminder_start,
            Match.scheduled_at <= reminder_end,
        )
        .all()
    )

    created_count = 0

    try:
        for match in matches:
            team_ids = {
                team_id
                for team_id in (match.team_a_id, match.team_b_id)
                if team_id is not None
            }

            if not team_ids:
                continue

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

            registrations = (
                db.query(Registration)
                .join(Player, Registration.player_id == Player.id)
                .filter(
                    Registration.tournament_id == match.tournament_id,
                    Registration.registration_type == "player",
                    Registration.status == "approved",
                    Player.team_id.in_(team_ids),
                )
                .all()
            )

            for registration in registrations:
                player = (
                    db.query(Player)
                    .filter(Player.id == registration.player_id)
                    .first()
                )

                if player is not None and player.user_id is not None:
                    recipient_ids.add(player.user_id)

            scheduled_time = match.scheduled_at

            if scheduled_time.tzinfo is None:
                scheduled_time_text = scheduled_time.strftime(
                    "%Y-%m-%d %H:%M"
                )
                time_zone_text = "server-local time"
            else:
                scheduled_time_text = scheduled_time.astimezone(
                    timezone.utc
                ).strftime("%Y-%m-%d %H:%M UTC")
                time_zone_text = "UTC"

            content = (
                f"Reminder: Match {match.match_number} "
                f"(Match ID {match.id}) is scheduled for "
                f"{scheduled_time_text} ({time_zone_text}). "
                f"Please prepare for your upcoming match."
            )

            for user_id in recipient_ids:
                existing = (
                    db.query(Notification)
                    .filter(
                        Notification.user_id == user_id,
                        Notification.notification_type
                        == REMINDER_NOTIFICATION_TYPE,
                        Notification.content == content,
                    )
                    .first()
                )

                if existing is not None:
                    continue

                notification = Notification(
                    user_id=user_id,
                    notification_type=REMINDER_NOTIFICATION_TYPE,
                    content=content,
                    is_read=False,
                )

                db.add(notification)
                created_count += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return created_count
