from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
)
from app.modules.player_team.models.team import Team
from app.modules.player_team.models.team import TeamStatus


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