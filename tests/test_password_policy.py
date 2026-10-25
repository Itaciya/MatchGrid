
import pytest
from pydantic import ValidationError

from app.modules.user.schemas.user import UserRegister
from app.core.security import hash_password, verify_password


@pytest.mark.parametrize(
    "password",
    [
        "password",
        "12345678",
        "password123",
        "qwerty123",
        "admin123",
        "abcdefgh",
    ],
)
def test_registration_rejects_weak_passwords(password):
    with pytest.raises(ValidationError):
        UserRegister(
            email="player@example.com",
            password=password,
            role="player",
        )


@pytest.mark.parametrize(
    "password",
    [
        "strongpassword123",
        "MatchGrid2026",
        "Player1234",
    ],
)
def test_registration_accepts_valid_passwords(password):
    user = UserRegister(
        email="player@example.com",
        password=password,
        role="player",
    )

    assert user.password == password
def test_password_is_hashed_and_can_be_verified():
    password = "strongpassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$2b$")
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword123", hashed)