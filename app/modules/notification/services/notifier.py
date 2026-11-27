"""Central place to create notifications and deliver them live.

Every notification row created through any session is pushed to its
recipient over WebSocket automatically, right after the transaction that
created it commits. Callers only add rows (with ``notify``) and commit as
usual; they never broadcast by hand, and a rolled-back transaction sends
nothing.
"""

import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.modules.notification.models.notification import Notification
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.models.tournament_follower import TournamentFollower

logger = logging.getLogger(__name__)

_PENDING_KEY = "matchgrid_pending_live_notifications"


# ---------------------------------------------------------------------------
# Creating notifications
# ---------------------------------------------------------------------------

def notify(
    db: Session,
    user_ids: Iterable[int | None],
    notification_type: str,
    content: str,
    link: str | None = None,
    *,
    exclude: Iterable[int | None] = (),
) -> int:
    """Add one notification per distinct recipient. Does not commit.

    Returns how many notifications were added.
    """
    skip = {user_id for user_id in exclude if user_id}
    recipients = sorted({user_id for user_id in user_ids if user_id} - skip)

    for user_id in recipients:
        db.add(
            Notification(
                user_id=user_id,
                notification_type=notification_type,
                content=content,
                link=link,
                is_read=False,
            )
        )

    return len(recipients)


# ---------------------------------------------------------------------------
# Audiences
# ---------------------------------------------------------------------------

def team_member_ids(db: Session, team_ids: Iterable[int | None]) -> set[int]:
    """Captains and players (with accounts) of the given teams."""
    ids = [team_id for team_id in team_ids if team_id]
    if not ids:
        return set()

    members = {
        captain_id
        for (captain_id,) in db.query(Team.captain_id).filter(Team.id.in_(ids))
        if captain_id
    }
    members.update(
        user_id
        for (user_id,) in db.query(Player.user_id).filter(Player.team_id.in_(ids))
        if user_id
    )
    return members


def follower_ids(db: Session, tournament_id: int) -> set[int]:
    """Users following a tournament (typically spectators)."""
    return {
        user_id
        for (user_id,) in db.query(TournamentFollower.user_id).filter(
            TournamentFollower.tournament_id == tournament_id
        )
    }


def organiser_id(db: Session, tournament_id: int) -> int | None:
    row = (
        db.query(Tournament.organizer_id)
        .filter(Tournament.id == tournament_id)
        .first()
    )
    return row[0] if row else None


def tournament_scorer_ids(db: Session, tournament_id: int) -> set[int]:
    """Scorers actively assigned to a tournament."""
    from app.modules.official_assignment.models.tournament_scorer_assignment import (
        TournamentScorerAssignment,
    )

    return {
        scorer_id
        for (scorer_id,) in db.query(TournamentScorerAssignment.scorer_id).filter(
            TournamentScorerAssignment.tournament_id == tournament_id,
            TournamentScorerAssignment.status == "active",
        )
    }


# ---------------------------------------------------------------------------
# Links into the frontend (hash routes)
# ---------------------------------------------------------------------------

def tournament_link(tournament_id: int) -> str:
    return f"#/details/{tournament_id}"


def approvals_link(tournament_id: int) -> str:
    return f"#/registration-approvals/{tournament_id}"


def verify_link(tournament_id: int) -> str:
    return f"#/verify/{tournament_id}"


MY_REGISTRATIONS_LINK = "#/registrations"
SCORING_LINK = "#/scoring"
DISPUTES_TO_RESOLVE_LINK = "#/resolve"
MY_DISPUTES_LINK = "#/dispute"


def match_label(match) -> str:
    """'Dhaka Dynamos vs Khulna Kings' (or the match number if teams are unknown)."""
    team_a = match.team_a.name if getattr(match, "team_a", None) else None
    team_b = match.team_b.name if getattr(match, "team_b", None) else None
    if team_a and team_b:
        return f"{team_a} vs {team_b}"
    return f"Match {match.match_number}"


# ---------------------------------------------------------------------------
# Live delivery after commit
# ---------------------------------------------------------------------------

def _live_event(notification: Notification) -> dict:
    """The WebSocket event for one notification, built from values already
    in memory (the row cannot be re-read once its transaction commits)."""
    return {
        "type": "notification:new",
        "payload": {
            "notification_id": notification.id,
            "recipient_id": notification.user_id,
            "title": notification.notification_type.replace("_", " ").title(),
            "message": notification.content,
            "notification_type": notification.notification_type,
            "link": notification.link,
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@event.listens_for(Session, "after_flush")
def _collect_new_notifications(session, flush_context):
    new_rows = [obj for obj in session.new if isinstance(obj, Notification)]
    if new_rows:
        session.info.setdefault(_PENDING_KEY, []).extend(
            _live_event(row) for row in new_rows
        )


@event.listens_for(Session, "after_commit")
def _deliver_committed_notifications(session):
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return

    from app.realtime.redis_pubsub import pubsub_manager

    # No running listener (e.g. scripts or tests without the app lifespan):
    # the notifications are stored and will be fetched normally.
    if pubsub_manager.event_loop is None:
        return

    for live_event in pending:
        try:
            pubsub_manager.schedule_event(live_event)
        except Exception:
            logger.exception("Could not schedule live notification delivery")


@event.listens_for(Session, "after_rollback")
def _discard_rolled_back_notifications(session):
    session.info.pop(_PENDING_KEY, None)
