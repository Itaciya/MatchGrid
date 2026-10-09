import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.core.security import decode_token
from app.data_access.database import get_db
from app.data_access.redis_client import get_redis
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import OfficialAssignment
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

bearer_scheme = HTTPBearer()


def _invalidated_after_key(user_id: str) -> str:
    return f"token_invalidated_after:{user_id}"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a bearer access token.

    Covers SCRUM-315 (user status validation): an inactive account's
    token is rejected here, even if the token itself is still valid.

    Covers SCRUM-51 (logout/token invalidation): a token issued before
    the user's most recent logout is rejected here too, even if it
    hasn't naturally expired yet.
    """
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise UnauthorizedException(detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise UnauthorizedException(detail="Invalid or expired token")

    user_id = payload.get("sub")

    redis_client = get_redis()
    invalidated_after = redis_client.get(_invalidated_after_key(user_id))

    if invalidated_after is not None and payload.get("iat", 0) <= int(invalidated_after):
        raise UnauthorizedException(detail="Invalid or expired token")

    user = db.query(User).filter(User.id == int(user_id)).first()

    if user is None:
        raise UnauthorizedException(detail="Invalid or expired token")

    if not user.is_active:
        raise UnauthorizedException(detail="Account is inactive")

    return user


def require_role(*allowed_roles: str):
    """Dependency factory: restrict an endpoint to specific user roles."""

    def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                detail="Your role does not permit this action"
            )
        return current_user

    return _check_role


def get_tournament_or_404(
    tournament_id: int,
    db: Session = Depends(get_db),
) -> Tournament:
    """Fetch a tournament by path param, or raise 404 if it doesn't exist."""
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    return tournament


def verify_tournament_owner(
    tournament: Tournament = Depends(get_tournament_or_404),
    current_user: User = Depends(require_role("organiser")),
) -> Tournament:
    """Ownership check for SCRUM-54: the organiser must own this specific
    tournament, not just hold the organiser role in general."""
    if tournament.organizer_id != current_user.id:
        raise ForbiddenException(detail="You do not own this tournament")

    return tournament


ASSIGNMENT_STATUS_ACTIVE = "active"


def verify_assigned_official(
    match_id: int,
    current_user: User = Depends(require_role("scorer", "official")),
    db: Session = Depends(get_db),
) -> Match:
    """SCRUM-144: the user must hold an official role AND have an active
    assignment to this specific match. Holding the role alone is not enough."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if match is None:
        raise NotFoundException(detail="Match not found")

    assignment = (
        db.query(OfficialAssignment)
        .filter(
            OfficialAssignment.match_id == match_id,
            OfficialAssignment.official_id == current_user.id,
            OfficialAssignment.status == ASSIGNMENT_STATUS_ACTIVE,
        )
        .first()
    )

    if assignment is None:
        raise ForbiddenException(detail="You are not assigned to this match")

    return match
