import pytest
from sqlalchemy.orm import Session
from app.data_access.database import engine, get_db
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.dispute.models.dispute import Dispute
from app.modules.match.models.match import Match
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)
@pytest.fixture
def db():
    """Use a rollbackable transaction for dispute endpoint tests."""
    connection = engine.connect()
    transaction = connection.begin()

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
        email=f"dispute_test_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def create_team(db, captain, prefix="Dispute Team"):
    team = Team(
        name=f"{prefix} {uuid4()}",
        captain_id=captain.id,
    )
    db.add(team)
    db.flush()
    return team


def create_player(db, user, team, player_status=PlayerStatus.ACTIVE):
    player = Player(
        user_id=user.id,
        team_id=team.id,
        first_name="Test",
        last_name="Player",
        status=player_status,
    )
    db.add(player)
    db.flush()
    return player


def create_match(db, organizer, team_a, team_b):
    tournament = Tournament(
        name=f"Dispute Tournament {uuid4()}",
        description="Test tournament",
        format="league",
        start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 1, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer.id,
    )
    db.add(tournament)
    db.flush()

    match = Match(
        tournament_id=tournament.id,
        match_number=1,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        status="scheduled",
    )
    db.add(match)
    db.flush()
    return match


def auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_active_participant_can_create_dispute(db):
    user = create_user(db)
    opponent = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")
    create_player(db, user, team_a)
    create_player(db, opponent, team_b)
    match = create_match(db, organizer, team_a, team_b)
    db.commit()

    response = client.post(
        "/disputes/",
        json={
            "match_id": match.id,
            "reason": "The recorded match result is incorrect.",
        },
        headers=auth_header(user),
    )

    assert response.status_code == 201
    assert response.json()["match_id"] == match.id
    assert response.json()["user_id"] == user.id
    assert response.json()["status"] == "pending"
    assert response.json()["reason"] == "The recorded match result is incorrect."


def test_non_participant_cannot_create_dispute(db):
    user = create_user(db)
    opponent = create_user(db)
    outsider = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")
    outsider_team = create_team(db, outsider, "Outsider Team")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)
    create_player(db, outsider, outsider_team)

    match = create_match(db, organizer, team_a, team_b)
    db.commit()

    response = client.post(
        "/disputes/",
        json={"match_id": match.id, "reason": "I am not in this match."},
        headers=auth_header(outsider),
    )

    assert response.status_code == 403


def test_inactive_player_cannot_create_dispute(db):
    user = create_user(db)
    opponent = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")
    create_player(db, user, team_a, PlayerStatus.INACTIVE)
    create_player(db, opponent, team_b)

    match = create_match(db, organizer, team_a, team_b)
    db.commit()

    response = client.post(
        "/disputes/",
        json={"match_id": match.id, "reason": "Please review this result."},
        headers=auth_header(user),
    )

    assert response.status_code == 403


def test_missing_match_is_rejected(db):
    user = create_user(db)
    db.commit()

    response = client.post(
        "/disputes/",
        json={"match_id": 999999999, "reason": "Please review this result."},
        headers=auth_header(user),
    )

    assert response.status_code == 404


def test_dispute_without_authentication_is_rejected():
    response = client.post(
        "/disputes/",
        json={"match_id": 1, "reason": "Please review this result."},
    )

    assert response.status_code == 401


def test_dispute_with_missing_reason_is_rejected(db):
    user = create_user(db)
    db.commit()

    response = client.post(
        "/disputes/",
        json={"match_id": 1},
        headers=auth_header(user),
    )

    assert response.status_code == 422
