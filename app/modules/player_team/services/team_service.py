from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundException
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