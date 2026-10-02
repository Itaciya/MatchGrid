from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)


def _make_user(db):
    user = User(
        email=f"details_test_{uuid4()}@example.com",
        password_hash="test-password-hash",
        role="organiser",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_tournament(db, organizer_id, **overrides):
    defaults = dict(
        name=f"Details Test Tournament {uuid4()}",
        description="Tournament details test",
        format="knockout",
        start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )
    defaults.update(overrides)

    tournament = Tournament(**defaults)
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def test_get_tournament_details_returns_correct_tournament(db):
    organiser = _make_user(db)
    tournament = _make_tournament(db, organiser.id)

    response = client.get(f"/tournaments/{tournament.id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == tournament.id
    assert data["name"] == tournament.name
    assert data["description"] == tournament.description
    assert data["format"] == tournament.format
    assert data["start_date"] == tournament.start_date.isoformat()
    assert data["end_date"] == tournament.end_date.isoformat()
    assert data["status"] == tournament.status
    assert data["organizer_id"] == organiser.id

    assert "created_at" in data
    assert "updated_at" in data


def test_get_tournament_details_returns_404_for_nonexistent_tournament(db):
    response = client.get("/tournaments/999999999")

    assert response.status_code == 404

    data = response.json()

    assert data["success"] is False
    assert data["error"]["type"] == "http_error"
    assert data["error"]["message"] == "Tournament not found"


def test_get_tournament_details_does_not_expose_restricted_user_information(db):
    organiser = _make_user(db)
    tournament = _make_tournament(db, organiser.id)

    response = client.get(f"/tournaments/{tournament.id}")

    assert response.status_code == 200

    data = response.json()

    assert "email" not in data
    assert "password_hash" not in data