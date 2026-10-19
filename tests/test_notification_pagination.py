import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.notification.models.notification import Notification
from app.modules.user.models import User

client = TestClient(app)


def _make_user(db, role="player"):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _add_notifications(db, user, count):
    created = []
    for index in range(count):
        notification = Notification(
            user_id=user.id,
            notification_type="test_notification",
            content=f"Message {index}",
            is_read=False,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        created.append(notification)
    return created


# SCRUM-235: retrieval, privacy and pagination

def test_user_only_receives_their_own_notifications(db):
    owner = _make_user(db)
    other = _make_user(db)
    _add_notifications(db, owner, 2)
    _add_notifications(db, other, 3)

    response = client.get("/notifications/", headers=_auth(owner))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert all(item["user_id"] == owner.id for item in body)


def test_limit_and_offset_paginate_without_overlap(db):
    user = _make_user(db)
    _add_notifications(db, user, 5)

    first = client.get("/notifications/?limit=2&offset=0", headers=_auth(user)).json()
    second = client.get("/notifications/?limit=2&offset=2", headers=_auth(user)).json()
    last = client.get("/notifications/?limit=2&offset=4", headers=_auth(user)).json()

    assert len(first) == 2
    assert len(second) == 2
    assert len(last) == 1
    ids = [item["id"] for item in first + second + last]
    assert len(set(ids)) == 5


def test_default_request_still_returns_everything(db):
    user = _make_user(db)
    _add_notifications(db, user, 4)

    response = client.get("/notifications/", headers=_auth(user))

    assert response.status_code == 200
    assert len(response.json()) == 4


def test_invalid_pagination_values_are_rejected(db):
    user = _make_user(db)

    assert client.get("/notifications/?limit=0", headers=_auth(user)).status_code == 422
    assert client.get("/notifications/?limit=101", headers=_auth(user)).status_code == 422
    assert client.get("/notifications/?offset=-1", headers=_auth(user)).status_code == 422


def test_unread_only_filter_still_works_with_pagination(db):
    user = _make_user(db)
    created = _add_notifications(db, user, 3)
    client.patch(f"/notifications/{created[0].id}/read", headers=_auth(user))

    response = client.get("/notifications/?unread_only=true&limit=10", headers=_auth(user))

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all(item["is_read"] is False for item in response.json())


def test_notifications_require_authentication(db):
    response = client.get("/notifications/")

    assert response.status_code in (401, 403)


# SCRUM-237: unread count and ownership

def test_unread_count_updates_after_marking_read(db):
    user = _make_user(db)
    created = _add_notifications(db, user, 3)

    before = client.get("/notifications/unread-count", headers=_auth(user))
    assert before.status_code == 200
    assert before.json() == {"unread_count": 3}

    marked = client.patch(f"/notifications/{created[0].id}/read", headers=_auth(user))
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True

    after = client.get("/notifications/unread-count", headers=_auth(user))
    assert after.json() == {"unread_count": 2}


def test_unread_count_only_counts_own_notifications(db):
    owner = _make_user(db)
    other = _make_user(db)
    _add_notifications(db, owner, 1)
    _add_notifications(db, other, 4)

    response = client.get("/notifications/unread-count", headers=_auth(owner))

    assert response.json() == {"unread_count": 1}


def test_unread_count_requires_authentication(db):
    response = client.get("/notifications/unread-count")

    assert response.status_code in (401, 403)


def test_cannot_mark_another_users_notification_as_read(db):
    owner = _make_user(db)
    intruder = _make_user(db)
    created = _add_notifications(db, owner, 1)

    response = client.patch(f"/notifications/{created[0].id}/read", headers=_auth(intruder))

    assert response.status_code == 404


def test_marking_a_missing_notification_is_rejected(db):
    user = _make_user(db)

    response = client.patch("/notifications/999999999/read", headers=_auth(user))

    assert response.status_code == 404