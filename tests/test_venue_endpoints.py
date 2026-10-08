from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_venues_without_authentication():
    response = client.get("/venues/")

    assert response.status_code == 200


def test_get_non_existing_venue():
    response = client.get("/venues/999999")

    assert response.status_code == 404


def test_create_venue_requires_authentication():
    response = client.post(
        "/venues/",
        json={
            "name": "Test Stadium",
            "location": "Dhaka",
            "description": "Test venue",
            "capacity": 5000,
        },
    )

    assert response.status_code == 401


def test_update_venue_requires_authentication():
    response = client.patch(
        "/venues/999999",
        json={
            "name": "Updated Stadium",
        },
    )

    assert response.status_code == 401


def test_delete_venue_requires_authentication():
    response = client.delete(
        "/venues/999999",
    )

    assert response.status_code == 401