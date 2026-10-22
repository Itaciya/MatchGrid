from uuid import uuid4

import pytest
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


ROLES = ["organiser", "player", "scorer", "spectator", "official"]


def _payload(**overrides):
    payload = {
        "email": _unique_email(),
        "password": "strongpassword123",
        "role": "player",
    }
    payload.update(overrides)
    return payload


# SCRUM-239: required fields

@pytest.mark.parametrize("missing", ["email", "password", "role"])
def test_register_missing_required_field_is_rejected(missing):
    payload = _payload()
    del payload[missing]

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_register_empty_body_is_rejected():
    response = client.post("/auth/register", json={})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": None},
        {"password": None},
        {"role": None},
        {"password": 12345678},
        {"role": 1},
    ],
)
def test_register_wrong_field_types_are_rejected(overrides):
    response = client.post("/auth/register", json=_payload(**overrides))

    assert response.status_code == 422


# SCRUM-239: roles and password limits

@pytest.mark.parametrize("role", ROLES)
def test_register_accepts_every_supported_role(role):
    response = client.post("/auth/register", json=_payload(role=role))

    assert response.status_code == 201
    assert response.json()["role"] == role


@pytest.mark.parametrize(
    "length, expected_status",
    [(7, 422), (8, 201), (72, 201), (73, 422)],
)
def test_register_password_length_boundaries(length, expected_status):
    # Keep the password within the length boundary while satisfying
    # the letter + number policy.
    password = "a" * (length - 1) + "1" if length >= 8 else "a" * length

    response = client.post(
        "/auth/register",
        json=_payload(password=password),
    )

    assert response.status_code == expected_status

# SCRUM-239: database records

def test_register_creates_one_database_record_with_the_right_values(db):
    email = _unique_email()

    response = client.post("/auth/register", json=_payload(email=email, role="scorer"))

    assert response.status_code == 201
    user = db.query(User).filter(User.email == email).one()
    assert user.role == "scorer"
    assert user.password_hash != "strongpassword123"


def test_duplicate_registration_creates_only_one_record(db):
    email = _unique_email()

    first = client.post("/auth/register", json=_payload(email=email))
    second = client.post("/auth/register", json=_payload(email=email, role="organiser"))

    assert first.status_code == 201
    assert second.status_code == 409
    users = db.query(User).filter(User.email == email).all()
    assert len(users) == 1
    assert users[0].role == "player"


def test_rejected_registration_creates_no_record(db):
    email = _unique_email()

    response = client.post("/auth/register", json=_payload(email=email, password="short"))

    assert response.status_code == 422
    assert db.query(User).filter(User.email == email).count() == 0


def test_registered_user_can_log_in(fake_redis):
    email = _unique_email()
    client.post("/auth/register", json=_payload(email=email))

    response = client.post(
        "/auth/login", json={"email": email, "password": "strongpassword123"}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()