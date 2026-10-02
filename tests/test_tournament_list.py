from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)


def _make_user(db):
    user = User(
        email=f"list_test_{uuid4()}@example.com",
        password_hash="test-password-hash",
        role="organiser",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_tournament(db, organizer_id, status):
    tournament = Tournament(
        name=f"List Test Tournament {uuid4()}",
        description="List test",
        format="knockout",
        start_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 7, 10, tzinfo=timezone.utc),
        status=status,
        organizer_id=organizer_id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def test_list_tournaments_returns_tournaments(db):
    organiser = _make_user(db)
    tournament = _make_tournament(db, organiser.id, "upcoming")

    response = client.get("/tournaments/")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 1

    returned = next(item for item in data if item["id"] == tournament.id)

    assert returned["name"] == tournament.name
    assert returned["format"] == tournament.format
    assert returned["status"] == "upcoming"
    assert returned["organizer_id"] == organiser.id


def test_list_tournaments_filters_by_status(db):
    organiser = _make_user(db)

    upcoming = _make_tournament(db, organiser.id, "upcoming")
    completed = _make_tournament(db, organiser.id, "completed")

    response = client.get("/tournaments/?status=upcoming")

    assert response.status_code == 200

    data = response.json()

    assert len(data) >= 1
    assert any(item["id"] == upcoming.id for item in data)
    assert all(item["status"] == "upcoming" for item in data)
    assert not any(item["id"] == completed.id for item in data)


def test_list_tournaments_returns_empty_list_when_no_match(db):
    organiser = _make_user(db)
    _make_tournament(db, organiser.id, "upcoming")

    response = client.get("/tournaments/?status=nonexistent")

    assert response.status_code == 200
    assert response.json() == []