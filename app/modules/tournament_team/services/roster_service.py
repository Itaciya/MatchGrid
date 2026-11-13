from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament_team.models.tournament_team import TournamentTeam
from app.modules.tournament_team.models.tournament_team_player import (
    TournamentTeamPlayer,
)


def _get_roster_context(
    db: Session,
    tournament_id: int,
    team_id: int,
    current_user_id: int,
    allow_locked: bool = False,
    lock_tournament: bool = False,
):
    tournament_query = db.query(Tournament).filter(
        Tournament.id == tournament_id
    )

    if lock_tournament:
        tournament_query = tournament_query.with_for_update()

    tournament = tournament_query.first()

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    if tournament.participation_type != "team":
        raise BadRequestException(
            detail="Player roster is only available for team tournaments"
        )

    team = db.query(Team).filter(Team.id == team_id).first()

    if team is None:
        raise NotFoundException(detail="Team not found")

    if team.captain_id != current_user_id:
        raise ForbiddenException(
            detail="Only the team captain can manage this tournament roster"
        )

    if team.status != TeamStatus.ACTIVE:
        raise ConflictException(
            detail="Only active teams can manage tournament rosters"
        )

    registration = (
        db.query(Registration)
        .filter(
            Registration.tournament_id == tournament_id,
            Registration.team_id == team_id,
            Registration.registration_type == "team",
            Registration.status == "approved",
        )
        .first()
    )

    if registration is None:
        raise ForbiddenException(
            detail="Team registration must be approved before managing its roster"
        )

    tournament_team = (
        db.query(TournamentTeam)
        .filter(
            TournamentTeam.tournament_id == tournament_id,
            TournamentTeam.team_id == team_id,
        )
        .first()
    )

    if tournament_team is None:
        raise NotFoundException(
            detail="Tournament team association not found"
        )

    if not allow_locked:
        if tournament.fixtures_published:
            raise ConflictException(
                detail="Tournament roster cannot be changed after fixtures are published"
            )

        if tournament.status in ("ongoing", "completed"):
            raise ConflictException(
                detail="Tournament roster cannot be changed after the tournament starts"
            )

    return tournament, team, tournament_team


def get_tournament_roster(
    db: Session,
    tournament_id: int,
    team_id: int,
    current_user_id: int,
) -> list[Player]:

    _, _, tournament_team = _get_roster_context(
        db,
        tournament_id,
        team_id,
        current_user_id,
        allow_locked=True,
    )

    return (
        db.query(Player)
        .join(
            TournamentTeamPlayer,
            TournamentTeamPlayer.player_id == Player.id,
        )
        .filter(
            TournamentTeamPlayer.tournament_id == tournament_id,
            TournamentTeamPlayer.tournament_team_id == tournament_team.id,
        )
        .order_by(Player.first_name.asc(), Player.last_name.asc())
        .all()
    )


def search_tournament_players(
    db: Session,
    tournament_id: int,
    team_id: int,
    current_user_id: int,
    search_term: str,
    limit: int = 20,
) -> list[Player]:

    _get_roster_context(
        db, tournament_id, team_id, current_user_id
    )

    search_term = search_term.strip()

    if not search_term:
        raise BadRequestException(detail="Search term cannot be empty")

    if len(search_term) > 100:
        raise BadRequestException(detail="Search term is too long")

    if search_term.isdigit():
        search_filter = or_(
            Player.user_id == int(search_term),
            func.concat(
                Player.first_name, " ", Player.last_name
            ).ilike(f"%{search_term}%"),
        )
    else:
        search_filter = func.concat(
            Player.first_name, " ", Player.last_name
        ).ilike(f"%{search_term}%")

    existing_player_ids = (
        db.query(TournamentTeamPlayer.player_id)
        .filter(
            TournamentTeamPlayer.tournament_id == tournament_id
        )
        .subquery()
    )

    return (
        db.query(Player)
        .filter(
            Player.status == PlayerStatus.ACTIVE,
            search_filter,
            ~Player.id.in_(
                db.query(existing_player_ids.c.player_id)
            ),
        )
        .order_by(Player.first_name.asc(), Player.last_name.asc())
        .limit(max(1, min(limit, 50)))
        .all()
    )


def add_player_to_tournament_roster(
    db: Session,
    tournament_id: int,
    team_id: int,
    player_id: int,
    current_user_id: int,
) -> TournamentTeamPlayer:

    tournament, _, tournament_team = _get_roster_context(
        db,
        tournament_id,
        team_id,
        current_user_id,
        lock_tournament=True,
    )

    player = db.query(Player).filter(Player.id == player_id).first()

    if player is None:
        raise NotFoundException(detail="Player not found")

    if player.status != PlayerStatus.ACTIVE:
        raise ConflictException(
            detail="Only active players can be added to a tournament roster"
        )

    existing_player = (
        db.query(TournamentTeamPlayer)
        .filter(
            TournamentTeamPlayer.tournament_id == tournament_id,
            TournamentTeamPlayer.player_id == player_id,
        )
        .first()
    )

    if existing_player is not None:
        raise ConflictException(
            detail="Player is already assigned to this tournament"
        )

    current_count = (
        db.query(TournamentTeamPlayer)
        .filter(
            TournamentTeamPlayer.tournament_team_id == tournament_team.id
        )
        .count()
    )

    if (
        tournament.max_roster_size is not None
        and current_count >= tournament.max_roster_size
    ):
        raise ConflictException(
            detail=f"Roster cannot contain more than {tournament.max_roster_size} players"
        )

    roster_entry = TournamentTeamPlayer(
        tournament_id=tournament_id,
        tournament_team_id=tournament_team.id,
        player_id=player_id,
        added_by_user_id=current_user_id,
    )

    try:
        db.add(roster_entry)
        db.commit()
        db.refresh(roster_entry)
    except IntegrityError:
        db.rollback()
        raise ConflictException(
            detail="Player is already assigned to this tournament"
        )

    return roster_entry


def remove_player_from_tournament_roster(
    db: Session,
    tournament_id: int,
    team_id: int,
    player_id: int,
    current_user_id: int,
) -> None:

    tournament, _, tournament_team = _get_roster_context(
        db,
        tournament_id,
        team_id,
        current_user_id,
        lock_tournament=True,
    )

    roster_entry = (
        db.query(TournamentTeamPlayer)
        .filter(
            TournamentTeamPlayer.tournament_id == tournament_id,
            TournamentTeamPlayer.tournament_team_id == tournament_team.id,
            TournamentTeamPlayer.player_id == player_id,
        )
        .first()
    )

    if roster_entry is None:
        raise NotFoundException(
            detail="Player not found in this tournament roster"
        )

    current_count = (
        db.query(TournamentTeamPlayer)
        .filter(
            TournamentTeamPlayer.tournament_team_id == tournament_team.id
        )
        .count()
    )

    if (
        tournament.min_roster_size is not None
        and current_count - 1 < tournament.min_roster_size
    ):
        raise ConflictException(
            detail=f"Roster must contain at least {tournament.min_roster_size} players"
        )

    try:
        db.delete(roster_entry)
        db.commit()
    except Exception:
        db.rollback()
        raise
