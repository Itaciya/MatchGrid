from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.user.models import User

client = TestClient(app)


def _unique_email():
    return f"register_test_{uuid4()}@example.com"


def test_register_valid_user_succeeds():
    email = _unique_email()
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "strongpassword123", "role": "player"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["role"] == "player"
    assert "password_hash" not in data
    assert "password" not in data


def test_register_duplicate_email_is_rejected():
    email = _unique_email()
    payload = {"email": email, "password": "strongpassword123", "role": "player"}

    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409


def test_register_invalid_email_is_rejected():
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "strongpassword123", "role": "player"},
    )
    assert response.status_code == 422


def test_register_short_password_is_rejected():
    response = client.post(
        "/auth/register",
        json={"email": _unique_email(), "password": "short", "role": "player"},
    )
    assert response.status_code == 422


def test_register_invalid_role_is_rejected():
    response = client.post(
        "/auth/register",
        json={"email": _unique_email(), "password": "strongpassword123", "role": "admin"},
    )
    assert response.status_code == 422


def test_registered_user_password_is_hashed_in_db(db):
    email = _unique_email()
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "strongpassword123", "role": "player"},
    )
    assert response.status_code == 201

    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.password_hash != "strongpassword123"
    assert user.password_hash.startswith("$2b$")
