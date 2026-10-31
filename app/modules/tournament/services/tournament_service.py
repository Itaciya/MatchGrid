
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.data_access.cache import delete_cached_keys
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import (
    TournamentCreate,
    TournamentUpdate,
)


TOURNAMENT_FORMATS = {
    "knockout",
    "round_robin",
    "league",
    "single_elimination",
    "double_elimination",
}

TOURNAMENT_STATUSES = {
    "upcoming",
    "ongoing",
    "completed",
    "archived",
}

VALID_STATUS_TRANSITIONS = {
    "upcoming": {"ongoing"},
    "ongoing": {"completed"},
    "completed": {"archived"},
    "archived": set(),
}


def invalidate_public_tournament_cache() -> None:
    """Invalidate cached public tournament lists."""
    delete_cached_keys(
        "spectator:tournaments:status:all",
        *(
            f"spectator:tournaments:status:{status}"
            for status in TOURNAMENT_STATUSES
        ),
        "spectator:tournaments:v3:status:all",
        *(
            f"spectator:tournaments:v3:status:{status}"
            for status in TOURNAMENT_STATUSES
        ),
    )


def validate_tournament_format(format: str) -> None:
    """Validate that a tournament format is supported."""
    if format not in TOURNAMENT_FORMATS:
        raise BadRequestException(
            detail=f"Invalid tournament format: {format}"
        )


def validate_tournament_format_config(
    format: str,
    format_config: dict | None,
) -> None:
    """Validate format-specific tournament configuration."""
    validate_tournament_format(format)

    if format == "round_robin":
        if format_config is None:
            raise BadRequestException(
                detail="Round-robin tournaments require format_config"
            )

        number_of_teams = format_config.get("number_of_teams")

        if number_of_teams is None:
            raise BadRequestException(
                detail="Round-robin configuration requires number_of_teams"
            )

        if number_of_teams < 2:
            raise BadRequestException(
                detail="Round-robin tournaments require at least 2 teams"
            )

    elif format == "single_elimination":
        if format_config is None:
            raise BadRequestException(
                detail="Single-elimination tournaments require format_config"
            )

        number_of_teams = format_config.get("number_of_teams")

        if number_of_teams is None:
            raise BadRequestException(
                detail=(
                    "Single-elimination configuration requires "
                    "number_of_teams"
                )
            )

        if number_of_teams < 2:
            raise BadRequestException(
                detail=(
                    "Single-elimination tournaments require "
                    "at least 2 teams"
                )
            )

    elif format == "double_elimination":
        if format_config is None:
            raise BadRequestException(
                detail=(
                    "Double-elimination tournaments require "
                    "format_config"
                )
            )

        number_of_teams = format_config.get("number_of_teams")

        if number_of_teams is None:
            raise BadRequestException(
                detail=(
                    "Double-elimination configuration requires "
                    "number_of_teams"
                )
            )

        if number_of_teams < 2:
            raise BadRequestException(
                detail=(
                    "Double-elimination tournaments require "
                    "at least 2 teams"
                )
            )

    elif format_config is not None:
        raise BadRequestException(
            detail=(
                "format_config is only supported for "
                "round_robin, single_elimination, and "
                "double_elimination tournaments"
            )
        )


def create_tournament(
    db: Session,
    organizer_id: int,
    data: TournamentCreate,
) -> Tournament:
    """Create a new tournament with upcoming status."""
    format_config = (
        data.format_config.model_dump()
        if data.format_config is not None
        else None
    )

    validate_tournament_format_config(
        data.format,
        format_config,
    )

    tournament = Tournament(
        name=data.name,
        category=data.category,
        participation_type=data.participation_type,
        description=data.description,
        format=data.format,
        format_config=format_config,
        start_date=data.start_date,
        end_date=data.end_date,
        registration_open_at=data.registration_open_at,
        registration_close_at=data.registration_close_at,
        status="upcoming",
        organizer_id=organizer_id,
    )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    invalidate_public_tournament_cache()

    return tournament


def update_tournament(
    db: Session,
    tournament: Tournament,
    data: TournamentUpdate,
) -> Tournament:
    """Apply a partial update to tournament details.

    Tournament status must be changed through the centralized
    status transition logic instead of a normal update.
    """
    updates = data.model_dump(exclude_unset=True)

    if "status" in updates:
        raise BadRequestException(
            detail="Tournament status cannot be changed through update"
        )

    new_start_date = updates.get(
        "start_date",
        tournament.start_date,
    )

    new_end_date = updates.get(
        "end_date",
        tournament.end_date,
    )

    if new_end_date <= new_start_date:
        raise BadRequestException(
            detail="end_date must be after start_date"
        )

    new_registration_open = updates.get(
        "registration_open_at",
        tournament.registration_open_at,
    )
    new_registration_close = updates.get(
        "registration_close_at",
        tournament.registration_close_at,
    )

    if new_registration_close <= new_registration_open:
        raise BadRequestException(
            detail="Registration closing must be after registration opening"
        )

    if new_registration_close > new_start_date:
        raise BadRequestException(
            detail="Registration must close before the tournament starts"
        )

    new_format = updates.get(
        "format",
        tournament.format,
    )

    if "format_config" in updates:
        new_format_config = updates["format_config"]
    else:
        new_format_config = tournament.format_config

    validate_tournament_format_config(
        new_format,
        new_format_config,
    )

    for field, value in updates.items():
        if field == "format_config":
            continue

        setattr(tournament, field, value)

    tournament.format = new_format
    tournament.format_config = new_format_config

    db.commit()
    db.refresh(tournament)

    invalidate_public_tournament_cache()

    return tournament


def validate_tournament_status(status: str) -> None:
    """Validate that a tournament status is supported."""
    if status not in TOURNAMENT_STATUSES:
        raise BadRequestException(
            detail=f"Invalid tournament status: {status}"
        )


def can_transition_tournament_status(
    current_status: str,
    new_status: str,
) -> bool:
    """Return whether a status transition is allowed."""
    validate_tournament_status(current_status)
    validate_tournament_status(new_status)

    return new_status in VALID_STATUS_TRANSITIONS[current_status]


def change_tournament_status(
    db: Session,
    tournament: Tournament,
    new_status: str,
) -> Tournament:
    """Change tournament status using the centralized transition rules."""
    validate_tournament_status(new_status)

    current_status = tournament.status

    if not can_transition_tournament_status(
        current_status,
        new_status,
    ):
        raise BadRequestException(
            detail=(
                f"Invalid tournament status transition: "
                f"{current_status} -> {new_status}"
            )
        )

    tournament.status = new_status

    db.commit()
    db.refresh(tournament)

    invalidate_public_tournament_cache()

    return tournament


def list_tournaments(
    db: Session,
    status: str | None = None,
) -> list[Tournament]:
    """Return tournaments, optionally filtered by status."""
    query = db.query(Tournament).filter(
        Tournament.status != "archived"
    )

    if status is not None:
        query = query.filter(
            Tournament.status == status
        )

    return query.order_by(
        Tournament.start_date.asc()
    ).all()


def get_tournament_by_id(
    db: Session,
    tournament_id: int,
) -> Tournament | None:
    """Return a tournament by ID, or None if it does not exist."""
    return (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )


def archive_tournament(
    db: Session,
    tournament: Tournament,
) -> Tournament:
    """Archive a completed tournament without deleting its history."""
    if tournament.status != "completed":
        raise BadRequestException(
            detail="Only completed tournaments can be archived"
        )

    return change_tournament_status(
        db,
        tournament,
        "archived",
    )
