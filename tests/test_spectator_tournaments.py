from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)


def create_organizer(db):
    user = User(
        email=f"spectator_{uuid4()}@example.com",
        password_hash="test-password-hash",
        role="organiser",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_tournament(db, organizer_id, status):
    tournament = Tournament(
        name=f"Spectator Tournament {uuid4()}",
        description="Spectator endpoint test",
        format="round_robin",
        start_date=datetime(2099, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, tzinfo=timezone.utc),
        status=status,
        organizer_id=organizer_id,
    
        registration_open_at=datetime(2098, 12, 1, 0, 0, tzinfo=timezone.utc),
        registration_close_at=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc))
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def test_spectator_can_list_tournaments(db):
    organizer = create_organizer(db)
    tournament = create_tournament(db, organizer.id, "upcoming")

    response = client.get("/spectator/tournaments")

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert any(item["id"] == tournament.id for item in data)


def test_spectator_can_filter_tournaments_by_status(db):
    organizer = create_organizer(db)

    upcoming = create_tournament(db, organizer.id, "upcoming")
    completed = create_tournament(db, organizer.id, "completed")

    response = client.get(
        "/spectator/tournaments",
        params={"status": "upcoming"},
    )

    assert response.status_code == 200

    data = response.json()
    returned_ids = {item["id"] for item in data}

    assert upcoming.id in returned_ids
    assert completed.id not in returned_ids
    assert all(item["status"] == "upcoming" for item in data)


def test_spectator_list_returns_empty_list_for_unmatched_status(db):
    organizer = create_organizer(db)
    create_tournament(db, organizer.id, "upcoming")

    response = client.get(
        "/spectator/tournaments",
        params={"status": "nonexistent"},
    )

    assert response.status_code == 200
    assert response.json() == []

def test_spectator_list_hides_archived_tournaments(db, monkeypatch):
    monkeypatch.setattr(
        "app.modules.spectator.routes.get_cached_json",
        lambda key: None,
    )
    monkeypatch.setattr(
        "app.modules.spectator.routes.set_cached_json",
        lambda *args, **kwargs: None,
    )
    organizer = create_organizer(db)

    upcoming = create_tournament(db, organizer.id, "upcoming")
    archived = create_tournament(db, organizer.id, "archived")

    response = client.get("/spectator/tournaments")

    assert response.status_code == 200

    returned_ids = {item["id"] for item in response.json()}
    assert upcoming.id in returned_ids
    assert archived.id not in returned_ids


def test_spectator_cannot_filter_archived_tournaments(db, monkeypatch):
    monkeypatch.setattr(
        "app.modules.spectator.routes.get_cached_json",
        lambda key: None,
    )
    monkeypatch.setattr(
        "app.modules.spectator.routes.set_cached_json",
        lambda *args, **kwargs: None,
    )
    organizer = create_organizer(db)
    archived = create_tournament(db, organizer.id, "archived")

    response = client.get(
        "/spectator/tournaments",
        params={"status": "archived"},
    )

    assert response.status_code == 200
    assert response.json() == []
    assert all(
        item["id"] != archived.id
        for item in response.json()
    )


def test_spectator_cannot_view_archived_tournament_details(db):
    organizer = create_organizer(db)
    archived = create_tournament(db, organizer.id, "archived")

    response = client.get(f"/spectator/tournaments/{archived.id}")

    assert response.status_code == 404
