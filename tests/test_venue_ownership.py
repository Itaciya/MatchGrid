from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.modules.user.models import User
from app.modules.venue.models.venue import Venue

client = TestClient(app)


def _organiser(db):
    user = User(
        email=f"venue_owner_{uuid4()}@example.com",
        password_hash="not-used",
        role="organiser",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _create_venue(owner):
    response = client.post(
        "/venues/",
        json={
            "name": f"Owned Venue {uuid4()}",
            "location": "North Stand",
            "capacity": 500,
        },
        headers=_headers(owner),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_created_venue_records_its_owner(db):
    owner = _organiser(db)

    venue = _create_venue(owner)

    assert venue["created_by_id"] == owner.id


def test_other_organiser_cannot_update_or_delete_venue(db):
    owner = _organiser(db)
    other = _organiser(db)
    venue = _create_venue(owner)

    update = client.patch(
        f"/venues/{venue['id']}",
        json={"capacity": 10},
        headers=_headers(other),
    )
    delete = client.delete(f"/venues/{venue['id']}", headers=_headers(other))

    assert update.status_code == 403
    assert delete.status_code == 403
    stored = db.query(Venue).filter(Venue.id == venue["id"]).one()
    assert stored.capacity == 500


def test_owner_can_update_and_delete_venue(db):
    owner = _organiser(db)
    venue = _create_venue(owner)

    update = client.patch(
        f"/venues/{venue['id']}",
        json={"capacity": 750},
        headers=_headers(owner),
    )
    delete = client.delete(f"/venues/{venue['id']}", headers=_headers(owner))

    assert update.status_code == 200
    assert update.json()["capacity"] == 750
    assert delete.status_code == 204
