
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.data_access.database import SessionLocal
from app.data_access.redis_client import get_redis
from app.modules.audit.services.audit_service import record_audit_event
from app.modules.user.models import User
from app.modules.user.schemas.user import TokenResponse, UserLogin

logger = logging.getLogger(__name__)


def _refresh_token_key(user_id: int) -> str:
    return f"refresh_token:{user_id}"


def _invalidated_after_key(user_id: int) -> str:
    return f"token_invalidated_after:{user_id}"


def _write_auth_audit_event(
    *,
    user_id: int,
    action: str,
) -> None:
    """Record an auth event without breaking authentication if auditing fails."""
    audit_db = SessionLocal()
    try:
        record_audit_event(
            audit_db,
            user_id=user_id,
            action=action,
            resource_type="user",
            resource_id=user_id,
        )
    except Exception:
        logger.exception("Failed to record authentication audit event")
    finally:
        audit_db.close()


def authenticate_user(db: Session, credentials: UserLogin) -> TokenResponse:
    """Verify credentials and issue an access/refresh token pair.

    Uses one generic error for both "no such user" and "wrong password"
    to avoid leaking which case applies.
    """
    user = db.query(User).filter(User.email == credentials.email).first()

    if user is None or not verify_password(
        credentials.password, user.password_hash
    ):
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

    _write_auth_audit_event(
        user_id=user.id,
        action="auth.login_success",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


def logout_user(user_id: int) -> None:
    """Invalidate the user's current session and record the logout event."""
    redis_client = get_redis()
    now = int(datetime.now(timezone.utc).timestamp())

    redis_client.set(
        _invalidated_after_key(user_id),
        str(now),
        ex=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    redis_client.delete(_refresh_token_key(user_id))

    _write_auth_audit_event(
        user_id=user_id,
        action="auth.logout",
    )
