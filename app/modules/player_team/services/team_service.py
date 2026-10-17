
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
)
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.user.models import User


def get_team(
    db: Session,
    team_id: int,
) -> Team:
    """Retrieve a team and its roster by team ID."""

    team = (
        db.query(Team)
        .options(selectinload(Team.players))
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(detail="Team not found")

    return team


def authorize_team_captain(
    db: Session,
    team_id: int,
    current_user_id: int,
    detail: str = "Only the team captain can manage this team",
) -> Team:
    """Verify that the current user is the captain of the team."""

    team = (
        db.query(Team)
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(detail="Team not found")

    if team.captain_id != current_user_id:
        raise ForbiddenException(detail=detail)

    return team


def create_team(
    db: Session,
    name: str,
    captain_id: int,
) -> Team:
    """Create a team after validating its captain and name."""

    # Check whether the captain exists.
    captain = (
        db.query(User)
        .filter(User.id == captain_id)
        .first()
    )

    if captain is None:
        raise NotFoundException(detail="Captain not found")

    # Check whether the team name already exists.
    existing_team = (
        db.query(Team)
        .filter(Team.name == name)
        .first()
    )

    if existing_team is not None:
        raise ForbiddenException(
            detail="A team with this name already exists"
        )

    # Create the new team.
    team = Team(
        name=name,
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )

    try:
        db.add(team)
        db.commit()
        db.refresh(team)

    except IntegrityError:
        db.rollback()
        raise ForbiddenException(
            detail="Team could not be created because its name already exists"
        )

    return team


def update_team_status(
    db: Session,
    team_id: int,
    status: TeamStatus,
) -> Team:
    """Update a team's status."""

    team = (
        db.query(Team)
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(detail="Team not found")

    team.status = status

    db.commit()
    db.refresh(team)

    return team
