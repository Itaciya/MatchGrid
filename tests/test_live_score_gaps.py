import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import OfficialAssignment
from app.modules.score.models.score import Score
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.realtime.connection_manager import manager

client = TestClient(app)

MAX_DB_INTEGER = 2147483647
SCORE_KEYS = {
    "id",
    "match_id",
    "team_a_score",
    "team_b_score",
    "is_verified",
    "verification_status",
    "reviewed_by_id",
    "reviewed_at",
    "created_at",
    "updated_at",
}


def _make_user(db, role):
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


def _auth_header(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _make_match(db, status="live"):
    organiser = _make_user(db, "organiser")
    tournament = Tournament(
        name=f"Live Score Gap Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    match = Match(
        tournament_id=tournament.id,
        match_number=1,
        scheduled_at=datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        status=status,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match.id


def _assigned_official(db, match_id, role="scorer"):
    user = _make_user(db, role)
    db.add(
        OfficialAssignment(
            match_id=match_id,
            official_id=user.id,
            assignment_type="referee",
            status="active",
        )
    )
    db.commit()
    return _auth_header(user)


def _make_score(db, match_id, a=1, b=0):
    score = Score(match_id=match_id, team_a_score=a, team_b_score=b)
    db.add(score)
    db.commit()
    return score


def _stored(db, match_id):
    db.expire_all()
    return db.query(Score).filter(Score.match_id == match_id).one()


def _score_count(db, match_id):
    return db.query(Score).filter(Score.match_id == match_id).count()


def _post(c, match_id, headers, a, b):
    return c.post(
        f"/matches/{match_id}/score",
        json={"match_id": match_id, "team_a_score": a, "team_b_score": b},
        headers=headers,
    )


def _patch(c, match_id, headers, body):
    return c.patch(f"/matches/{match_id}/score", json=body, headers=headers)


def _run_concurrently(calls):
    barrier = threading.Barrier(len(calls))

    def worker(call):
        local_client = TestClient(app)
        barrier.wait(timeout=30)
        return call(local_client)

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(worker, calls))


# SCRUM-249: response shape and stored values

def test_submit_response_has_the_full_score_shape_and_starts_unverified(db):
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)

    response = _post(client, match_id, headers, 3, 2)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == SCORE_KEYS
    assert body["match_id"] == match_id
    assert (body["team_a_score"], body["team_b_score"]) == (3, 2)
    assert body["is_verified"] is False
    assert body["verification_status"] == "pending"
    assert body["reviewed_by_id"] is None
    assert body["reviewed_at"] is None


def test_update_response_has_the_same_shape_and_the_new_values(db):
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)
    _make_score(db, match_id, 1, 0)

    response = _patch(client, match_id, headers, {"team_a_score": 4, "team_b_score": 3})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == SCORE_KEYS
    assert (body["team_a_score"], body["team_b_score"]) == (4, 3)
    stored = _stored(db, match_id)
    assert (stored.team_a_score, stored.team_b_score) == (4, 3)


def test_updating_a_score_to_zero_is_stored_as_zero_not_ignored(db):
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)
    _make_score(db, match_id, 3, 2)

    response = _patch(client, match_id, headers, {"team_a_score": 0})

    assert response.status_code == 200
    stored = _stored(db, match_id)
    assert (stored.team_a_score, stored.team_b_score) == (0, 2)


# SCRUM-249: boundary values

def test_largest_database_integer_is_accepted_and_stored(db):
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)

    response = _post(client, match_id, headers, MAX_DB_INTEGER, MAX_DB_INTEGER)

    assert response.status_code == 201
    stored = _stored(db, match_id)
    assert stored.team_a_score == MAX_DB_INTEGER


def test_score_above_the_database_limit_is_rejected_on_submit(db):
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)
    safe_client = TestClient(app, raise_server_exceptions=False)

    response = _post(safe_client, match_id, headers, MAX_DB_INTEGER + 1, 0)

    assert response.status_code == 422
    assert _score_count(db, match_id) == 0


def test_score_above_the_database_limit_is_rejected_on_update(db):
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)
    _make_score(db, match_id, 1, 1)
    safe_client = TestClient(app, raise_server_exceptions=False)

    response = _patch(safe_client, match_id, headers, {"team_a_score": MAX_DB_INTEGER + 1})

    assert response.status_code == 422
    stored = _stored(db, match_id)
    assert (stored.team_a_score, stored.team_b_score) == (1, 1)


# SCRUM-249: concurrent requests

def test_simultaneous_first_submissions_create_exactly_one_score(db, monkeypatch):
    monkeypatch.setattr(manager, "broadcast_to_match", AsyncMock())
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)

    responses = _run_concurrently(
        [lambda c, a=i: _post(c, match_id, headers, a, 0) for i in range(6)]
    )

    assert sorted(r.status_code for r in responses) == [201] + [409] * 5
    assert _score_count(db, match_id) == 1
    winner = next(r for r in responses if r.status_code == 201).json()
    assert _stored(db, match_id).team_a_score == winner["team_a_score"]


def test_simultaneous_submissions_by_two_officials_create_one_score(db, monkeypatch):
    monkeypatch.setattr(manager, "broadcast_to_match", AsyncMock())
    match_id = _make_match(db)
    first = _assigned_official(db, match_id, "scorer")
    second = _assigned_official(db, match_id, "official")

    responses = _run_concurrently(
        [
            lambda c: _post(c, match_id, first, 1, 0),
            lambda c: _post(c, match_id, second, 0, 1),
            lambda c: _post(c, match_id, first, 2, 0),
            lambda c: _post(c, match_id, second, 0, 2),
        ]
    )

    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]
    assert _score_count(db, match_id) == 1


def test_simultaneous_updates_never_mix_two_requests_values(db, monkeypatch):
    monkeypatch.setattr(manager, "broadcast_to_match", AsyncMock())
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)
    _make_score(db, match_id, 0, 0)
    pairs = [(i, 100 + i) for i in range(1, 7)]

    responses = _run_concurrently(
        [
            lambda c, a=a, b=b: _patch(
                c, match_id, headers, {"team_a_score": a, "team_b_score": b}
            )
            for a, b in pairs
        ]
    )

    assert all(r.status_code == 200 for r in responses)
    stored = _stored(db, match_id)
    assert (stored.team_a_score, stored.team_b_score) in pairs
    assert _score_count(db, match_id) == 1


def test_simultaneous_partial_updates_do_not_lose_either_change(db, monkeypatch):
    monkeypatch.setattr(manager, "broadcast_to_match", AsyncMock())
    match_id = _make_match(db)
    headers = _assigned_official(db, match_id)
    _make_score(db, match_id, 0, 0)

    responses = _run_concurrently(
        [
            lambda c: _patch(c, match_id, headers, {"team_a_score": 11}),
            lambda c: _patch(c, match_id, headers, {"team_b_score": 22}),
        ]
    )

    assert all(r.status_code == 200 for r in responses)
    stored = _stored(db, match_id)
    assert (stored.team_a_score, stored.team_b_score) == (11, 22)


def test_simultaneous_submissions_for_different_matches_do_not_interfere(db, monkeypatch):
    monkeypatch.setattr(manager, "broadcast_to_match", AsyncMock())
    setups = []
    for _ in range(4):
        match_id = _make_match(db)
        setups.append((match_id, _assigned_official(db, match_id)))

    responses = _run_concurrently(
        [
            lambda c, m=m, h=h, a=i: _post(c, m, h, a, a + 1)
            for i, (m, h) in enumerate(setups)
        ]
    )

    assert all(r.status_code == 201 for r in responses)
    for index, (match_id, _) in enumerate(setups):
        stored = _stored(db, match_id)
        assert (stored.team_a_score, stored.team_b_score) == (index, index + 1)