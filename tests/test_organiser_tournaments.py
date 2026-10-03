
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)


def _make_user(db, role="organiser", **overrides):
    defaults = dict(
        email=f"organiser_test_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_tournament(db, organizer_id, **overrides):
    defaults = dict(
        name=f"Test Tournament {uuid4()}",
        description="Test",
        format="knockout",
        start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 6, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )
    defaults.update(overrides)
    tournament = Tournament(**defaults)
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _valid_payload():
    return {
        "name": f"New Tournament {uuid4()}",
        "description": "A test tournament",
        "format": "knockout",
        "start_date": "2026-07-01T00:00:00Z",
        "end_date": "2026-07-10T00:00:00Z",
    }


def test_organiser_can_create_tournament(db):
    organiser = _make_user(db, role="organiser")

    response = client.post(
        "/organiser/tournaments",
        json=_valid_payload(),
        headers=_auth_header(organiser),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["organizer_id"] == organiser.id
    assert data["status"] == "upcoming"

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == data["id"])
        .first()
    )

    assert tournament is not None
    assert tournament.organizer_id == organiser.id
    assert tournament.status == "upcoming"


def test_non_organiser_cannot_create_tournament(db):
    player = _make_user(db, role="player")

    response = client.post(
        "/organiser/tournaments",
        json=_valid_payload(),
        headers=_auth_header(player),
    )

    assert response.status_code == 403


def test_create_tournament_without_token_is_rejected():
    response = client.post(
        "/organiser/tournaments",
        json=_valid_payload(),
    )

    assert response.status_code == 401


def test_create_tournament_rejects_end_date_before_start_date(db):
    organiser = _make_user(db, role="organiser")

    payload = _valid_payload()
    payload["start_date"] = "2026-07-10T00:00:00Z"
    payload["end_date"] = "2026-07-01T00:00:00Z"

    response = client.post(
        "/organiser/tournaments",
        json=payload,
        headers=_auth_header(organiser),
    )

    assert response.status_code == 422


def test_organiser_can_update_own_tournament(db):
    organiser = _make_user(db, role="organiser")
    tournament = _make_tournament(db, organiser.id)

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}",
        json={"name": f"Updated Name {uuid4()}"},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 200
    assert response.json()["name"].startswith("Updated Name")


def test_organiser_cannot_update_others_tournament(db):
    owner = _make_user(db, role="organiser")
    other_organiser = _make_user(db, role="organiser")
    tournament = _make_tournament(db, owner.id)

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}",
        json={"name": "Hijacked Name"},
        headers=_auth_header(other_organiser),
    )

    assert response.status_code == 403


def test_update_nonexistent_tournament_returns_404(db):
    organiser = _make_user(db, role="organiser")

    response = client.patch(
        "/organiser/tournaments/999999",
        json={"name": "Does not matter"},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 404


def test_non_organiser_cannot_update_any_tournament(db):
    owner = _make_user(db, role="organiser")
    player = _make_user(db, role="player")
    tournament = _make_tournament(db, owner.id)

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}",
        json={"name": "Should not work"},
        headers=_auth_header(player),
    )

    assert response.status_code == 403


def test_organiser_update_rejects_invalid_dates(db):
    organiser = _make_user(db, role="organiser")
    tournament = _make_tournament(db, organiser.id)

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}",
        json={
            "start_date": "2026-07-10T00:00:00Z",
            "end_date": "2026-07-01T00:00:00Z",
        },
        headers=_auth_header(organiser),
    )

    assert response.status_code == 422


def test_organiser_update_rejects_invalid_partial_date_update(db):
    organiser = _make_user(db, role="organiser")
    tournament = _make_tournament(db, organiser.id)

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}",
        json={
            "start_date": "2026-06-15T00:00:00Z",
        },
        headers=_auth_header(organiser),
    )

    assert response.status_code == 400


def test_organiser_can_archive_own_completed_tournament(db):
    organiser = _make_user(db, role="organiser")

    tournament = _make_tournament(
        db,
        organiser.id,
        status="completed",
    )

    original_name = tournament.name
    original_description = tournament.description
    original_format = tournament.format
    original_start_date = tournament.start_date
    original_end_date = tournament.end_date

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}/archive",
        headers=_auth_header(organiser),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == tournament.id
    assert data["status"] == "archived"

    archived_tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament.id)
        .first()
    )

    assert archived_tournament is not None

    db.refresh(archived_tournament)

    assert archived_tournament.status == "archived"

    # Historical tournament information must remain unchanged.
    assert archived_tournament.name == original_name
    assert archived_tournament.description == original_description
    assert archived_tournament.format == original_format
    assert archived_tournament.start_date == original_start_date
    assert archived_tournament.end_date == original_end_date
    assert archived_tournament.organizer_id == organiser.id


def test_organiser_cannot_archive_upcoming_tournament(db):
    organiser = _make_user(db, role="organiser")

    tournament = _make_tournament(
        db,
        organiser.id,
        status="upcoming",
    )

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}/archive",
        headers=_auth_header(organiser),
    )

    assert response.status_code == 400

    data = response.json()

    assert data["success"] is False
    assert data["error"]["type"] == "application_error"
    assert data["error"]["message"] == (
        "Only completed tournaments can be archived"
    )

    db.refresh(tournament)

    assert tournament.status == "upcoming"


def test_organiser_cannot_archive_others_tournament(db):
    owner = _make_user(db, role="organiser")
    other_organiser = _make_user(db, role="organiser")

    tournament = _make_tournament(
        db,
        owner.id,
        status="completed",
    )

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}/archive",
        headers=_auth_header(other_organiser),
    )

    assert response.status_code == 403

    db.refresh(tournament)

    assert tournament.status == "completed"


def test_non_organiser_cannot_archive_tournament(db):
    owner = _make_user(db, role="organiser")
    player = _make_user(db, role="player")

    tournament = _make_tournament(
        db,
        owner.id,
        status="completed",
    )

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}/archive",
        headers=_auth_header(player),
    )

    assert response.status_code == 403

    db.refresh(tournament)

    assert tournament.status == "completed"


def test_archive_tournament_without_token_is_rejected(db):
    organiser = _make_user(db, role="organiser")

    tournament = _make_tournament(
        db,
        organiser.id,
        status="completed",
    )

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}/archive",
    )

    assert response.status_code == 401


def test_archive_nonexistent_tournament_returns_404(db):
    organiser = _make_user(db, role="organiser")

    response = client.patch(
        "/organiser/tournaments/999999/archive",
        headers=_auth_header(organiser),
    )

    assert response.status_code == 404


def test_archived_tournament_cannot_be_archived_again(db):
    organiser = _make_user(db, role="organiser")

    tournament = _make_tournament(
        db,
        organiser.id,
        status="archived",
    )

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}/archive",
        headers=_auth_header(organiser),
    )

    assert response.status_code == 400

    data = response.json()

    assert data["success"] is False
    assert data["error"]["type"] == "application_error"
    assert data["error"]["message"] == (
        "Only completed tournaments can be archived"
    )

    db.refresh(tournament)

    assert tournament.status == "archived"


def test_organiser_cannot_change_tournament_status_through_update(db):
    organiser = _make_user(db, role="organiser")

    tournament = _make_tournament(
        db,
        organiser.id,
        status="upcoming",
    )

    response = client.patch(
        f"/organiser/tournaments/{tournament.id}",
        json={"status": "completed"},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 400

    db.refresh(tournament)

    assert tournament.status == "upcoming"
