import pytest
from pydantic import ValidationError

from app.modules.user.schemas.user import UserRegister, UserLogin, UserResponse


# --- UserRegister ---

def test_valid_registration_passes():
    user = UserRegister(
        email="player1@example.com",
        password="strongpassword123",
        role="player",
    )
    assert user.email == "player1@example.com"
    assert user.role == "player"


def test_registration_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserRegister(
            email="not-an-email",
            password="strongpassword123",
            role="player",
        )


def test_registration_rejects_short_password():
    with pytest.raises(ValidationError):
        UserRegister(
            email="player1@example.com",
            password="short",
            role="player",
        )


def test_registration_rejects_invalid_role():
    with pytest.raises(ValidationError):
        UserRegister(
            email="player1@example.com",
            password="strongpassword123",
            role="admin",
        )


@pytest.mark.parametrize(
    "role", ["organiser", "player", "scorer", "spectator", "official"]
)
def test_registration_accepts_each_valid_role(role):
    user = UserRegister(
        email="user@example.com",
        password="strongpassword123",
        role=role,
    )
    assert user.role == role


# --- UserLogin ---

def test_valid_login_passes():
    login = UserLogin(email="player1@example.com", password="anypassword")
    assert login.email == "player1@example.com"


def test_login_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserLogin(email="not-an-email", password="anypassword")


# --- UserResponse ---

def test_response_schema_excludes_password_hash():
    assert "password_hash" not in UserResponse.model_fields


def test_response_schema_serializes_from_orm_like_object():
    class FakeUser:
        id = 1
        email = "player1@example.com"
        role = "player"
        is_active = True
        created_at = "2026-01-01T00:00:00Z"
        updated_at = "2026-01-01T00:00:00Z"

    response = UserResponse.model_validate(FakeUser())
    assert response.id == 1
    assert response.email == "player1@example.com"
    assert not hasattr(response, "password_hash")


def test_registration_rejects_password_over_72_chars():
    with pytest.raises(ValidationError):
        UserRegister(
            email="player1@example.com",
            password="a" * 73,
            role="player",
        )
