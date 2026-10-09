from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.modules.player_team.models.team import Team
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import RegistrationStatus


def validate_team_for_fixture(
    db: Session,
    tournament_id: int,
    team_id: int,
) -> Team:
    team = (
        db.query(Team)
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(
            detail=f"Team with ID {team_id} was not found"
        )

    registration = (
        db.query(Registration)
        .filter(
            Registration.tournament_id == tournament_id,
            Registration.team_id == team_id,
        )
        .first()
    )

    if registration is None:
        raise BadRequestException(
            detail=(
                f"Team with ID {team_id} is not registered "
                f"for tournament {tournament_id}"
            )
        )

    if registration.status != RegistrationStatus.APPROVED.value:
        raise BadRequestException(
            detail=(
                f"Team with ID {team_id} is not approved "
                "for fixture generation"
            )
        )

    return team


def validate_teams_for_fixture(
    db: Session,
    tournament_id: int,
    team_ids: list[int],
) -> list[Team]:
    if not team_ids or len(team_ids) < 2:
        raise BadRequestException(
            detail="At least two teams are required for fixture generation"
        )

    if len(team_ids) != len(set(team_ids)):
        raise BadRequestException(
            detail="Duplicate team IDs are not allowed in fixture generation"
        )

    validated_teams = []

    for team_id in team_ids:
        team = validate_team_for_fixture(
            db,
            tournament_id,
            team_id,
        )
        validated_teams.append(team)

    return validated_teams