from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import (
    OfficialAssignment,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


ASSIGNMENT_STATUS_ACTIVE = "active"
MATCH_DURATION = timedelta(hours=1)

ASSIGNMENT_ROLE_MAP = {
    "referee": "official",
    "scorer": "scorer",
}


def assign_official(
    db: Session,
    tournament_id: int,
    match_id: int,
    official_id: int,
    assignment_type: str,
) -> OfficialAssignment:
    """Assign an eligible official to a match owned by the organizer."""

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
            detail="Match not found in this tournament"
        )

    if assignment_type not in ASSIGNMENT_ROLE_MAP:
        raise BadRequestException(
            detail="Assignment type must be referee or scorer"
        )

    official = (
        db.query(User)
        .filter(User.id == official_id)
        .first()
    )

    if official is None:
        raise NotFoundException(detail="Staff member not found")

    if not official.is_active:
        raise BadRequestException(
            detail="Inactive staff cannot be assigned"
        )

    expected_role = ASSIGNMENT_ROLE_MAP[assignment_type]

    if official.role != expected_role:
        raise BadRequestException(
            detail=(
                f"A {assignment_type} assignment requires "
                f"a user with role '{expected_role}'"
            )
        )

    if match.status != "scheduled":
        raise BadRequestException(
            detail="Staff can only be assigned to scheduled matches"
        )

    # Prevent duplicate assignments of the same staff member to this match.
    existing_assignment = (
        db.query(OfficialAssignment)
        .filter(
            OfficialAssignment.match_id == match_id,
            OfficialAssignment.official_id == official_id,
        )
        .first()
    )

    if existing_assignment is not None:
        raise ConflictException(
            detail="This staff member already has an assignment for this match"
        )

    # Prevent overlapping active assignments for the same staff member.
    window_start = match.scheduled_at - MATCH_DURATION
    window_end = match.scheduled_at + MATCH_DURATION

    conflicting_assignment = (
        db.query(OfficialAssignment)
        .join(
            Match,
            OfficialAssignment.match_id == Match.id,
        )
        .filter(
            OfficialAssignment.official_id == official_id,
            OfficialAssignment.status == ASSIGNMENT_STATUS_ACTIVE,
            Match.id != match_id,
            Match.status.in_(["scheduled", "live"]),
            Match.scheduled_at > window_start,
            Match.scheduled_at < window_end,
        )
        .first()
    )

    if conflicting_assignment is not None:
        raise ConflictException(
            detail=(
                "This staff member already has an overlapping "
                "active match assignment"
            )
        )

    assignment = OfficialAssignment(
        match_id=match_id,
        official_id=official_id,
        assignment_type=assignment_type,
        status=ASSIGNMENT_STATUS_ACTIVE,
    )

    db.add(assignment)

    try:
        db.commit()
        db.refresh(assignment)
    except IntegrityError:
        db.rollback()
        raise ConflictException(
            detail="A duplicate or conflicting assignment already exists"
        )

    return assignment


def get_my_assigned_matches(
    db: Session,
    official: User,
) -> list[dict]:
    """Return active assignments and match details for the current staff user."""

    assignments = (
        db.query(OfficialAssignment, Match)
        .join(
            Match,
            OfficialAssignment.match_id == Match.id,
        )
        .filter(
            OfficialAssignment.official_id == official.id,
            OfficialAssignment.status == ASSIGNMENT_STATUS_ACTIVE,
        )
        .order_by(Match.scheduled_at, Match.match_number)
        .all()
    )

    return [
        {
            "id": match.id,
            "tournament_id": match.tournament_id,
            "match_number": match.match_number,
            "team_a_id": match.team_a_id,
            "team_b_id": match.team_b_id,
            "venue_id": match.venue_id,
            "scheduled_at": match.scheduled_at,
            "status": match.status,
            "assignment_type": assignment.assignment_type,
        }
        for assignment, match in assignments
    ]