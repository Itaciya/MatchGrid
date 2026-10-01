from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.data_access.database import get_db
from app.modules.user.models import User
from app.modules.user.schemas.user import TokenResponse, UserLogin, UserRegister, UserResponse
from app.modules.user.services.auth_service import authenticate_user, logout_user
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
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    current_user: User = Depends(get_current_user),
):
    """Invalidate the current session (SCRUM-51)."""
    logout_user(current_user.id)


@router.get(
    "/me",
    response_model=UserResponse,
)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    """Protected route: proves the authentication dependency works end-to-end."""
    return current_user
