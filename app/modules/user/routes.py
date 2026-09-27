from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.data_access.database import get_db
from app.modules.user.schemas.user import UserRegister, UserResponse
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
