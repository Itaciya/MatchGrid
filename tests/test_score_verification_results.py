import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import OfficialAssignment
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.score.models.score import Score
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.services.standings_service import (
    calculate_tournament_standings,
)
from app.modules.tournament_team.models.tournament_team import TournamentTeam
from app.modules.user.models import User
from app.realtime.connection_manager import manager

client = TestClient(app)


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


def _setup(db, match_count=1):
    """A tournament with two registered teams and live matches between them."""
    organiser = _make_user(db, "organiser")
    tournament = Tournament(
        name=f"Verification Results Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    team_a = Team(name=f"Verif Team A {uuid.uuid4()}", captain_id=organiser.id, status=TeamStatus.ACTIVE)
    team_b = Team(name=f"Verif Team B {uuid.uuid4()}", captain_id=organiser.id, status=TeamStatus.ACTIVE)
    db.add_all([team_a, team_b])
    db.commit()
    db.refresh(team_a)
    db.refresh(team_b)

    db.add_all(
        [
            TournamentTeam(tournament_id=tournament.id, team_id=team_a.id),
            TournamentTeam(tournament_id=tournament.id, team_id=team_b.id),
        ]
    )

    matches = [
        Match(
            tournament_id=tournament.id,
            match_number=index + 1,
            team_a_id=team_a.id,
            team_b_id=team_b.id,
            scheduled_at=datetime(2099, 1, 2 + index, 10, 0, tzinfo=timezone.utc),
            status="live",
        )
        for index in range(match_count)
    ]
    db.add_all(matches)
    db.commit()
    for match in matches:
        db.refresh(match)

    return SimpleNamespace(
        organiser_id=organiser.id,
        headers=_auth_header(organiser),
        tournament_id=tournament.id,
        a_id=team_a.id,
        b_id=team_b.id,
        match_ids=[m.id for m in matches],
    )


def _make_score(db, match_id, a, b):
    score = Score(match_id=match_id, team_a_score=a, team_b_score=b)
    db.add(score)
    db.commit()


def _stored(db, match_id):
    db.expire_all()
    return db.query(Score).filter(Score.match_id == match_id).one()


def _review(c, match_id, headers, decision):
    return c.patch(
        f"/matches/{match_id}/score/verification",
        json={"status": decision},
        headers=headers,
    )


def _complete(db, match_id):
    """Mark the match completed, as finalization does."""
    match = db.query(Match).filter(Match.id == match_id).one()
    match.status = "completed"
    db.commit()


def _standings(db, tournament_id):
    db.expire_all()
    return {
        row["team_id"]: row
        for row in calculate_tournament_standings(db, tournament_id)
    }


def _assign(db, match_id, role="scorer"):
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


def _run_concurrently(calls):
    barrier = threading.Barrier(len(calls))

    def worker(call):
        local_client = TestClient(app)
        barrier.wait(timeout=30)
        return call(local_client)

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(worker, calls))


# SCRUM-250: what approval and rejection store

def test_approval_records_the_reviewer_and_keeps_the_score_values(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)

    response = _review(client, mid, s.headers, "verified")

    assert response.status_code == 200
    body = response.json()
    assert body["is_verified"] is True
    assert body["verification_status"] == "verified"
    stored = _stored(db, mid)
    assert stored.is_verified is True
    assert stored.reviewed_by_id == s.organiser_id
    assert stored.reviewed_at is not None
    assert (stored.team_a_score, stored.team_b_score) == (3, 1)


def test_rejected_score_stays_unverified_and_records_the_reviewer(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)

    response = _review(client, mid, s.headers, "rejected")

    assert response.status_code == 200
    body = response.json()
    assert body["is_verified"] is False
    assert body["verification_status"] == "rejected"
    stored = _stored(db, mid)
    assert stored.is_verified is False
    assert stored.reviewed_by_id == s.organiser_id
    assert stored.reviewed_at is not None
    assert (stored.team_a_score, stored.team_b_score) == (3, 1)


def test_pending_score_is_unverified_and_has_no_reviewer(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)

    stored = _stored(db, mid)

    assert stored.verification_status == "pending"
    assert stored.is_verified is False
    assert stored.reviewed_by_id is None
    assert stored.reviewed_at is None


# SCRUM-250: only verified scores affect official results

def test_pending_score_does_not_affect_standings(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 5, 0)
    _complete(db, mid)

    standings = _standings(db, s.tournament_id)

    for team_id in (s.a_id, s.b_id):
        assert standings[team_id]["played"] == 0
        assert standings[team_id]["points"] == 0


def test_rejected_score_does_not_affect_standings(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 5, 0)
    assert _review(client, mid, s.headers, "rejected").status_code == 200
    _complete(db, mid)

    standings = _standings(db, s.tournament_id)

    for team_id in (s.a_id, s.b_id):
        assert standings[team_id]["played"] == 0
        assert standings[team_id]["points"] == 0


def test_verified_score_of_a_match_that_is_not_completed_does_not_count(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 5, 0)
    assert _review(client, mid, s.headers, "verified").status_code == 200

    standings = _standings(db, s.tournament_id)

    assert standings[s.a_id]["played"] == 0
    assert standings[s.a_id]["points"] == 0


def test_verified_win_counts_for_the_standings(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)
    assert _review(client, mid, s.headers, "verified").status_code == 200
    _complete(db, mid)

    standings = _standings(db, s.tournament_id)

    winner, loser = standings[s.a_id], standings[s.b_id]
    assert (winner["played"], winner["wins"], winner["points"]) == (1, 1, 3)
    assert (winner["score_for"], winner["score_against"]) == (3, 1)
    assert (loser["played"], loser["losses"], loser["points"]) == (1, 1, 0)
    assert winner["rank"] == 1


def test_verified_draw_gives_each_team_one_point(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 2, 2)
    assert _review(client, mid, s.headers, "verified").status_code == 200
    _complete(db, mid)

    standings = _standings(db, s.tournament_id)

    for team_id in (s.a_id, s.b_id):
        assert standings[team_id]["draws"] == 1
        assert standings[team_id]["points"] == 1


def test_only_the_verified_match_counts_when_others_are_pending_or_rejected(db):
    s = _setup(db, match_count=3)
    verified, pending, rejected = s.match_ids
    _make_score(db, verified, 2, 0)
    _make_score(db, pending, 9, 0)
    _make_score(db, rejected, 4, 0)
    assert _review(client, verified, s.headers, "verified").status_code == 200
    assert _review(client, rejected, s.headers, "rejected").status_code == 200
    for match_id in s.match_ids:
        _complete(db, match_id)

    standings = _standings(db, s.tournament_id)

    assert standings[s.a_id]["played"] == 1
    assert standings[s.a_id]["points"] == 3
    assert standings[s.a_id]["score_for"] == 2
    assert standings[s.b_id]["score_against"] == 2


def test_standings_use_the_corrected_values_after_reject_correct_and_reverify(db):
    s = _setup(db)
    mid = s.match_ids[0]
    official = _assign(db, mid)
    _make_score(db, mid, 5, 0)
    assert _review(client, mid, s.headers, "rejected").status_code == 200

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(manager, "broadcast_to_match", AsyncMock())
        corrected = client.patch(
            f"/matches/{mid}/score",
            json={"team_a_score": 1, "team_b_score": 2},
            headers=official,
        )
    assert corrected.status_code == 200
    assert corrected.json()["verification_status"] == "pending"

    assert _review(client, mid, s.headers, "verified").status_code == 200
    _complete(db, mid)

    standings = _standings(db, s.tournament_id)

    assert standings[s.b_id]["wins"] == 1
    assert standings[s.b_id]["points"] == 3
    assert standings[s.a_id]["losses"] == 1
    assert standings[s.a_id]["score_for"] == 1


def test_a_rejected_score_cannot_be_forced_to_verified_to_reach_the_standings(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 5, 0)
    assert _review(client, mid, s.headers, "rejected").status_code == 200

    response = _review(client, mid, s.headers, "verified")

    assert response.status_code == 409
    assert _stored(db, mid).is_verified is False
    _complete(db, mid)
    assert _standings(db, s.tournament_id)[s.a_id]["points"] == 0


def test_a_verified_score_cannot_be_rejected_afterwards_and_still_counts(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 2, 1)
    assert _review(client, mid, s.headers, "verified").status_code == 200

    response = _review(client, mid, s.headers, "rejected")

    assert response.status_code == 409
    assert _stored(db, mid).is_verified is True
    _complete(db, mid)
    assert _standings(db, s.tournament_id)[s.a_id]["points"] == 3


@pytest.mark.parametrize(
    "decision,expected_a,expected_b",
    [("verified", 3, 0), ("rejected", 0, 0), (None, 0, 0)],
)
def test_public_standings_only_reflect_verified_scores(db, decision, expected_a, expected_b):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)
    if decision is not None:
        assert _review(client, mid, s.headers, decision).status_code == 200
    _complete(db, mid)
    tournament = db.query(Tournament).filter(Tournament.id == s.tournament_id).one()
    tournament.fixtures_published = True
    db.commit()

    response = client.get(f"/tournaments/{s.tournament_id}/standings")

    assert response.status_code == 200
    rows = {row["team_id"]: row for row in response.json()}
    assert rows[s.a_id]["points"] == expected_a
    assert rows[s.b_id]["points"] == expected_b


# SCRUM-250: security

def test_review_body_cannot_set_the_reviewer_or_verified_flag(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)

    response = client.patch(
        f"/matches/{mid}/score/verification",
        json={"status": "verified", "reviewed_by_id": 1, "is_verified": True},
        headers=s.headers,
    )

    assert response.status_code == 422
    stored = _stored(db, mid)
    assert stored.verification_status == "pending"
    assert stored.is_verified is False
    assert stored.reviewed_by_id is None


def test_deactivated_organiser_cannot_review_a_score(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)
    organiser = db.query(User).filter(User.id == s.organiser_id).one()
    organiser.is_active = False
    db.commit()

    response = _review(client, mid, s.headers, "verified")

    assert response.status_code == 401
    assert _stored(db, mid).verification_status == "pending"


# SCRUM-250: concurrent reviews

@pytest.mark.parametrize("attempt", range(3))
def test_simultaneous_approve_and_reject_leave_one_consistent_decision(db, attempt):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)

    responses = _run_concurrently(
        [
            lambda c: _review(c, mid, s.headers, "verified"),
            lambda c: _review(c, mid, s.headers, "rejected"),
        ]
    )

    assert sorted(r.status_code for r in responses) == [200, 409]
    decided = next(r for r in responses if r.status_code == 200).json()["verification_status"]
    stored = _stored(db, mid)
    assert stored.verification_status == decided
    assert stored.is_verified == (decided == "verified")


def test_repeated_simultaneous_approvals_succeed_exactly_once(db):
    s = _setup(db)
    mid = s.match_ids[0]
    _make_score(db, mid, 3, 1)

    responses = _run_concurrently(
        [lambda c: _review(c, mid, s.headers, "verified") for _ in range(5)]
    )

    assert sorted(r.status_code for r in responses) == [200] + [409] * 4
    stored = _stored(db, mid)
    assert stored.is_verified is True
    assert stored.reviewed_by_id == s.organiser_id


@pytest.mark.parametrize("attempt", range(3))
def test_review_racing_with_an_update_never_leaves_a_mixed_state(db, monkeypatch, attempt):
    monkeypatch.setattr(manager, "broadcast_to_match", AsyncMock())
    s = _setup(db)
    mid = s.match_ids[0]
    official = _assign(db, mid)
    _make_score(db, mid, 1, 0)

    update, review = _run_concurrently(
        [
            lambda c: c.patch(
                f"/matches/{mid}/score",
                json={"team_a_score": 7, "team_b_score": 8},
                headers=official,
            ),
            lambda c: _review(c, mid, s.headers, "verified"),
        ]
    )

    assert review.status_code == 200
    assert update.status_code in (200, 409)
    stored = _stored(db, mid)
    assert stored.is_verified is True
    expected = (7, 8) if update.status_code == 200 else (1, 0)
    assert (stored.team_a_score, stored.team_b_score) == expected