from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.data_access.redis_client import get_redis
from app.modules.user.models import User
from app.modules.user.schemas.user import TokenResponse, UserLogin


def _refresh_token_key(user_id: int) -> str:
    return f"refresh_token:{user_id}"


def authenticate_user(db: Session, credentials: UserLogin) -> TokenResponse:
    """Verify credentials and issue an access/refresh token pair.

    Uses one generic error for both "no such user" and "wrong password"
    to avoid leaking which case applies (account enumeration protection).
    Inactive accounts get a distinct message -- that is account status,
    not an enumeration risk.
    """
    user = db.query(User).filter(User.email == credentials.email).first()

    if user is None or not verify_password(credentials.password, user.password_hash):
        raise UnauthorizedException(detail="Invalid email or password")

    if not user.is_active:
        raise UnauthorizedException(detail="Account is inactive")

    access_token = create_access_token(user.id, user.role)
    refresh_token, jti = create_refresh_token(user.id)

    redis_client = get_redis()
    redis_client.set(
        _refresh_token_key(user.id),
        jti,
        ex=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
