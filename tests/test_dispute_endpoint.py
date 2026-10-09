from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.data_access.database import engine, get_db
from app.main import app
from app.modules.dispute.models.dispute import Dispute
from app.modules.dispute.models.dispute_status_history import (
    DisputeStatusHistory,
)
from app.modules.match.models.match import Match
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.player_team.models.team import Team
from app.modules.score.models.score import Score
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)


@pytest.fixture
def db():
    """Use a rollbackable transaction for dispute endpoint tests."""
    connection = engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


def create_user(db, role="player"):
    user = User(
        email=f"dispute_test_{uuid4()}@example.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def create_team(db, captain, prefix="Dispute Team"):
    team = Team(
        name=f"{prefix} {uuid4()}",
        captain_id=captain.id,
    )
    db.add(team)
    db.flush()
    return team


def create_player(
    db,
    user,
    team,
    player_status=PlayerStatus.ACTIVE,
):
    player = Player(
        user_id=user.id,
        team_id=team.id,
        first_name="Test",
        last_name="Player",
        status=player_status,
    )
    db.add(player)
    db.flush()
    return player


def create_match(db, organizer, team_a, team_b):
    tournament = Tournament(
        name=f"Dispute Tournament {uuid4()}",
        description="Test tournament",
        format="league",
        start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 1, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer.id,
    )
    db.add(tournament)
    db.flush()

    match = Match(
        tournament_id=tournament.id,
        match_number=1,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        status="scheduled",
    )
    db.add(match)
    db.flush()
    return match


def auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# Dispute creation tests
# ============================================================


def test_active_participant_can_create_dispute(db):
    user = create_user(db)
    opponent = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organizer, team_a, team_b)
    db.commit()

    response = client.post(
        "/disputes/",
        json={
            "match_id": match.id,
            "reason": "The recorded match result is incorrect.",
        },
        headers=auth_header(user),
    )

    assert response.status_code == 201
    assert response.json()["match_id"] == match.id
    assert response.json()["user_id"] == user.id
    assert response.json()["status"] == "pending"
    assert (
        response.json()["reason"]
        == "The recorded match result is incorrect."
    )


def test_non_participant_cannot_create_dispute(db):
    user = create_user(db)
    opponent = create_user(db)
    outsider = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")
    outsider_team = create_team(db, outsider, "Outsider Team")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)
    create_player(db, outsider, outsider_team)

    match = create_match(db, organizer, team_a, team_b)
    db.commit()

    response = client.post(
        "/disputes/",
        json={
            "match_id": match.id,
            "reason": "I am not in this match.",
        },
        headers=auth_header(outsider),
    )

    assert response.status_code == 403


def test_inactive_player_cannot_create_dispute(db):
    user = create_user(db)
    opponent = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(
        db,
        user,
        team_a,
        PlayerStatus.INACTIVE,
    )
    create_player(db, opponent, team_b)

    match = create_match(db, organizer, team_a, team_b)
    db.commit()

    response = client.post(
        "/disputes/",
        json={
            "match_id": match.id,
            "reason": "Please review this result.",
        },
        headers=auth_header(user),
    )

    assert response.status_code == 403


def test_missing_match_is_rejected(db):
    user = create_user(db)
    db.commit()

    response = client.post(
        "/disputes/",
        json={
            "match_id": 999999999,
            "reason": "Please review this result.",
        },
        headers=auth_header(user),
    )

    assert response.status_code == 404


def test_dispute_without_authentication_is_rejected():
    response = client.post(
        "/disputes/",
        json={
            "match_id": 1,
            "reason": "Please review this result.",
        },
    )

    assert response.status_code == 401


def test_dispute_with_missing_reason_is_rejected(db):
    user = create_user(db)
    db.commit()

    response = client.post(
        "/disputes/",
        json={"match_id": 1},
        headers=auth_header(user),
    )

    assert response.status_code == 422


# ============================================================
# Dispute retrieval tests
# ============================================================


def test_dispute_owner_can_retrieve_dispute_by_id(db):
    user = create_user(db)
    opponent = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organizer, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="The match result is incorrect.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.get(
        f"/disputes/{dispute.id}",
        headers=auth_header(user),
    )

    assert response.status_code == 200
    assert response.json()["id"] == dispute.id
    assert response.json()["match_id"] == match.id
    assert response.json()["reason"] == "The match result is incorrect."
    assert response.json()["status"] == "pending"


def test_missing_dispute_returns_404(db):
    user = create_user(db)
    db.commit()

    response = client.get(
        "/disputes/999999999",
        headers=auth_header(user),
    )

    assert response.status_code == 404


def test_non_participant_cannot_retrieve_dispute(db):
    owner = create_user(db)
    opponent = create_user(db)
    outsider = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, owner, "Team A")
    team_b = create_team(db, opponent, "Team B")
    outsider_team = create_team(db, outsider, "Outsider Team")

    create_player(db, owner, team_a)
    create_player(db, opponent, team_b)
    create_player(db, outsider, outsider_team)

    match = create_match(db, organizer, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=owner.id,
        reason="Please review this result.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.get(
        f"/disputes/{dispute.id}",
        headers=auth_header(outsider),
    )

    assert response.status_code == 403


def test_match_participant_can_retrieve_disputes_by_match(db):
    user = create_user(db)
    opponent = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organizer, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="Please review this match.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.get(
        f"/disputes/match/{match.id}",
        headers=auth_header(user),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == dispute.id
    assert response.json()[0]["match_id"] == match.id


def test_non_participant_cannot_retrieve_match_disputes(db):
    owner = create_user(db)
    opponent = create_user(db)
    outsider = create_user(db)
    organizer = create_user(db, role="organiser")

    team_a = create_team(db, owner, "Team A")
    team_b = create_team(db, opponent, "Team B")
    outsider_team = create_team(db, outsider, "Outsider Team")

    create_player(db, owner, team_a)
    create_player(db, opponent, team_b)
    create_player(db, outsider, outsider_team)

    match = create_match(db, organizer, team_a, team_b)
    db.commit()

    response = client.get(
        f"/disputes/match/{match.id}",
        headers=auth_header(outsider),
    )

    assert response.status_code == 403


def test_retrieving_dispute_without_authentication_returns_401():
    response = client.get("/disputes/999999999")

    assert response.status_code == 401


# ============================================================
# Dispute status transition tests
# ============================================================


def test_tournament_owner_can_move_dispute_to_under_review(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="The match result is incorrect.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.patch(
        f"/disputes/{dispute.id}/status",
        json={"status": "under_review"},
        headers=auth_header(organiser),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "under_review"

    history = (
        db.query(DisputeStatusHistory)
        .filter(DisputeStatusHistory.dispute_id == dispute.id)
        .all()
    )

    assert len(history) == 1
    assert history[0].previous_status == "pending"
    assert history[0].new_status == "under_review"
    assert history[0].changed_by == organiser.id


def test_cannot_skip_dispute_review_stage(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="The match result is incorrect.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.patch(
        f"/disputes/{dispute.id}/status",
        json={"status": "resolved"},
        headers=auth_header(organiser),
    )

    assert response.status_code == 403

    db.refresh(dispute)
    assert dispute.status == "pending"

    history = (
        db.query(DisputeStatusHistory)
        .filter(DisputeStatusHistory.dispute_id == dispute.id)
        .all()
    )

    assert len(history) == 0


# ============================================================
# Organizer dispute review tests - Subtask 1
# ============================================================


def test_organiser_can_view_own_pending_disputes_with_match_info(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="The match result is incorrect.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.get(
        "/disputes/pending",
        headers=auth_header(organiser),
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body) == 1
    assert body[0]["id"] == dispute.id
    assert body[0]["status"] == "pending"
    assert body[0]["match"]["id"] == match.id
    assert body[0]["match"]["team_a_id"] == team_a.id
    assert body[0]["match"]["team_b_id"] == team_b.id
    assert body[0]["result"] is None


def test_player_cannot_access_organiser_pending_disputes(db):
    player = create_user(db)

    response = client.get(
        "/disputes/pending",
        headers=auth_header(player),
    )

    assert response.status_code == 403


def test_organiser_cannot_see_another_organisers_pending_disputes(db):
    user = create_user(db)
    opponent = create_user(db)
    owner = create_user(db, role="organiser")
    another_organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, owner, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="Please review this result.",
        status="pending",
    )
    db.add(dispute)
    db.commit()

    response = client.get(
        "/disputes/pending",
        headers=auth_header(another_organiser),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_organiser_can_view_pending_dispute_with_score(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    score = Score(
        match_id=match.id,
        team_a_score=2,
        team_b_score=1,
        is_verified=False,
        verification_status="pending",
    )
    db.add(score)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="The submitted result may be incorrect.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.get(
        "/disputes/pending",
        headers=auth_header(organiser),
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body) == 1
    assert body[0]["match"]["team_a_name"] == team_a.name
    assert body[0]["match"]["team_b_name"] == team_b.name
    assert body[0]["result"]["team_a_score"] == 2
    assert body[0]["result"]["team_b_score"] == 1
    assert body[0]["result"]["verification_status"] == "pending"


# ============================================================
# Dispute resolution tests - Subtask 2
# ============================================================


def test_organiser_can_resolve_dispute_and_save_resolution(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="The match result is incorrect.",
        status="under_review",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.patch(
        f"/disputes/{dispute.id}/resolve",
        json={
            "decision": "resolved",
            "resolution": "The match result was reviewed and corrected.",
        },
        headers=auth_header(organiser),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert (
        response.json()["resolution"]
        == "The match result was reviewed and corrected."
    )

    db.refresh(dispute)
    assert dispute.status == "resolved"
    assert (
        dispute.resolution
        == "The match result was reviewed and corrected."
    )

    history = (
        db.query(DisputeStatusHistory)
        .filter(DisputeStatusHistory.dispute_id == dispute.id)
        .all()
    )

    assert len(history) == 1
    assert history[0].previous_status == "under_review"
    assert history[0].new_status == "resolved"
    assert history[0].changed_by == organiser.id


def test_organiser_can_reject_dispute_with_resolution(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="The result should be changed.",
        status="under_review",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.patch(
        f"/disputes/{dispute.id}/resolve",
        json={
            "decision": "rejected",
            "resolution": (
                "The submitted evidence does not support the complaint."
            ),
        },
        headers=auth_header(organiser),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert (
        response.json()["resolution"]
        == "The submitted evidence does not support the complaint."
    )


def test_another_organiser_cannot_resolve_dispute(db):
    user = create_user(db)
    opponent = create_user(db)
    owner = create_user(db, role="organiser")
    another_organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, owner, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="Please review this result.",
        status="under_review",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.patch(
        f"/disputes/{dispute.id}/resolve",
        json={
            "decision": "resolved",
            "resolution": "Reviewed by another organiser.",
        },
        headers=auth_header(another_organiser),
    )

    assert response.status_code == 403

    db.refresh(dispute)
    assert dispute.status == "under_review"
    assert dispute.resolution is None


def test_pending_dispute_cannot_be_resolved_directly(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="Please review this result.",
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.patch(
        f"/disputes/{dispute.id}/resolve",
        json={
            "decision": "resolved",
            "resolution": "Attempted direct resolution.",
        },
        headers=auth_header(organiser),
    )

    assert response.status_code == 403

    db.refresh(dispute)
    assert dispute.status == "pending"
    assert dispute.resolution is None


def test_invalid_resolution_decision_is_rejected(db):
    user = create_user(db)
    opponent = create_user(db)
    organiser = create_user(db, role="organiser")

    team_a = create_team(db, user, "Team A")
    team_b = create_team(db, opponent, "Team B")

    create_player(db, user, team_a)
    create_player(db, opponent, team_b)

    match = create_match(db, organiser, team_a, team_b)

    dispute = Dispute(
        match_id=match.id,
        user_id=user.id,
        reason="Please review this result.",
        status="under_review",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    response = client.patch(
        f"/disputes/{dispute.id}/resolve",
        json={
            "decision": "approved",
            "resolution": "Invalid decision.",
        },
        headers=auth_header(organiser),
    )

    assert response.status_code == 422

    db.refresh(dispute)
    assert dispute.status == "under_review"
    assert dispute.resolution is None