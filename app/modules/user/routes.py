from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.data_access.database import get_db
from app.modules.user.models import User
from app.modules.user.schemas.user import (
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.modules.user.services.auth_service import (
    authenticate_user,
    logout_user,
    refresh_tokens,
)
from app.modules.user.services.user_service import register_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    return register_user(db, user_data)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    return authenticate_user(db, credentials)


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
def refresh(
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Exchange a refresh token for a new access/refresh pair."""
    return refresh_tokens(db, data.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    current_user: User = Depends(get_current_user),
):
    """Invalidate the current session."""
    logout_user(current_user.id)


@router.get(
    "/me",
    response_model=UserResponse,
)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user."""
    return current_user


