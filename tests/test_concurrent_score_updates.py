
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import (
    OfficialAssignment,
)
from app.modules.score.models.score import Score
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)


def _make_user(db, role):
    user = User(
        email=f"{uuid.uuid4().hex}@concurrency-test.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _make_live_match(db):
    organiser = _make_user(db, "organiser")

    tournament = Tournament(
        name=f"Concurrency Test {uuid.uuid4().hex}",
        format="round_robin",
        start_date=datetime(
            2099, 1, 1, 10, 0, tzinfo=timezone.utc
        ),
        end_date=datetime(
            2099, 1, 10, 18, 0, tzinfo=timezone.utc
        ),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    match = Match(
        tournament_id=tournament.id,
        match_number=1,
        scheduled_at=datetime(
            2099, 1, 2, 10, 0, tzinfo=timezone.utc
        ),
        status="live",
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    return match


def _assign_scorer(db, match):
    scorer = _make_user(db, "scorer")

    assignment = OfficialAssignment(
        match_id=match.id,
        official_id=scorer.id,
        assignment_type="referee",
        status="active",
    )
    db.add(assignment)
    db.commit()

    return scorer


def _make_score(db, match, team_a=1, team_b=0):
    score = Score(
        match_id=match.id,
        team_a_score=team_a,
        team_b_score=team_b,
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


def _run_concurrently(request_functions):
    barrier = Barrier(len(request_functions))

    def run_request(request_function):
        barrier.wait(timeout=15)
        return request_function()

    with ThreadPoolExecutor(
        max_workers=len(request_functions)
    ) as executor:
        futures = [
            executor.submit(run_request, request_function)
            for request_function in request_functions
        ]
        return [future.result(timeout=60) for future in futures]


def test_concurrent_score_updates_are_persisted_safely(db):
    match = _make_live_match(db)
    scorer = _assign_scorer(db, match)
    _make_score(db, match, team_a=1, team_b=0)

    headers = _auth_header(scorer)

    def update_score(team_a, team_b):
        return lambda: client.patch(
            f"/matches/{match.id}/score",
            json={
                "team_a_score": team_a,
                "team_b_score": team_b,
            },
            headers=headers,
        )

    responses = _run_concurrently(
        [
            update_score(5, 2),
            update_score(7, 3),
        ]
    )

    assert all(response.status_code == 200 for response in responses), [
        (response.status_code, response.text)
        for response in responses
    ]

    db.expire_all()
    saved_score = (
        db.query(Score)
        .filter(Score.match_id == match.id)
        .one()
    )

    # Both requests update the same score row. The final state must
    # match one complete request, not a partially mixed result.
    assert (
        saved_score.team_a_score,
        saved_score.team_b_score,
    ) in {(5, 2), (7, 3)}


def test_concurrent_score_submissions_create_only_one_score(db):
    match = _make_live_match(db)
    scorer = _assign_scorer(db, match)
    headers = _auth_header(scorer)

    def submit_score(team_a, team_b):
        return lambda: client.post(
            f"/matches/{match.id}/score",
            json={
                "match_id": match.id,
                "team_a_score": team_a,
                "team_b_score": team_b,
            },
            headers=headers,
        )

    responses = _run_concurrently(
        [
            submit_score(2, 1),
            submit_score(4, 3),
        ]
    )

    statuses = sorted(
        response.status_code for response in responses
    )

    assert statuses == [201, 409], [
        (response.status_code, response.text)
        for response in responses
    ]

    db.expire_all()
    scores = (
        db.query(Score)
        .filter(Score.match_id == match.id)
        .all()
    )

    assert len(scores) == 1
