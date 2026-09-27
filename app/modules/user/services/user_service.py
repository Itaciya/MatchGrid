from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.core.security import hash_password
from app.modules.user.models import User
from app.modules.user.schemas.user import UserRegister


def register_user(db: Session, user_data: UserRegister) -> User:
    """Register a new user. Raises ConflictException if the email is taken."""
    existing_user = db.query(User).filter(User.email == user_data.email).first()

    if existing_user is not None:
        raise ConflictException(detail="Email is already registered")

    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user
