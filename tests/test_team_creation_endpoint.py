from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.data_access.database import engine, get_db
from app.main import app
from app.modules.player_team.models.team import Team
from app.modules.user.models import User


client = TestClient(app)


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()

    from sqlalchemy.orm import Session

    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


def create_user(db, role="player"):
    user = User(
        email=f"team_create_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_player_can_create_team_and_becomes_captain(db):
    captain = create_user(db, role="player")

    response = client.post(
        "/player-team/team",
        json={
            "name": f"Integration Team {uuid4()}",
        },
        headers=auth_header(captain),
    )

    assert response.status_code == 201
    assert response.json()["captain_id"] == captain.id
    assert response.json()["status"] == "active"


def test_team_creation_uses_logged_in_player_as_captain(db):
    captain = create_user(db, role="player")

    response = client.post(
        "/player-team/team",
        json={
            "name": f"Missing Captain Team {uuid4()}",
        },
        headers=auth_header(captain),
    )

    assert response.status_code == 201
    assert response.json()["captain_id"] == captain.id


def test_team_creation_rejects_duplicate_name(db):
    captain = create_user(db, role="player")
    team_name = f"Duplicate Team {uuid4()}"

    existing_team = Team(
        name=team_name,
        captain_id=captain.id,
    )
    db.add(existing_team)
    db.flush()

    response = client.post(
        "/player-team/team",
        json={
            "name": team_name,
        },
        headers=auth_header(captain),
    )

    assert response.status_code in (403, 409)
    assert "already exists" in response.json()["error"]["message"]


def test_organiser_cannot_create_team(db):
    organiser = create_user(db, role="organiser")

    response = client.post(
        "/player-team/team",
        json={
            "name": f"Unauthorized Team {uuid4()}",
        },
        headers=auth_header(organiser),
    )

    assert response.status_code == 403


def test_team_creation_requires_authentication(db):
    captain = create_user(db, role="player")

    response = client.post(
        "/player-team/team",
        json={
            "name": f"Unauthenticated Team {uuid4()}",
        },
    )

    assert response.status_code == 401
