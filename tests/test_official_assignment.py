import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.official_assignment.models.official_assignment import (
    OfficialAssignment,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


client = TestClient(app)


def create_user(db, role="organiser", is_active=True):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash=hash_password("correctpassword123"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"Official Assignment Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def create_match(db, tournament_id, match_number=1, scheduled_at=None):
    match = Match(
        tournament_id=tournament_id,
        match_number=match_number,
        scheduled_at=scheduled_at
        or datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        status="scheduled",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def assignment_url(tournament_id, match_id):
    return (
        f"/official-assignments/tournaments/{tournament_id}"
        f"/matches/{match_id}"
    )


def assign(organiser, tournament, match, official, assignment_type="referee"):
    return client.post(
        assignment_url(tournament.id, match.id),
        headers=auth_header(organiser),
        json={
            "official_id": official.id,
            "assignment_type": assignment_type,
        },
    )


def test_organiser_can_assign_referee_successfully(db):
    organiser = create_user(db, "organiser")
    referee = create_user(db, "official")
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    response = assign(organiser, tournament, match, referee)

    assert response.status_code == 201
    data = response.json()
    assert data["match_id"] == match.id
    assert data["official_id"] == referee.id
    assert data["assignment_type"] == "referee"
    assert data["status"] == "active"

    assignment = (
        db.query(OfficialAssignment)
        .filter(OfficialAssignment.id == data["id"])
        .first()
    )
    assert assignment is not None


def test_organiser_can_assign_scorer_successfully(db):
    organiser = create_user(db, "organiser")
    scorer = create_user(db, "scorer")
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    response = assign(
        organiser, tournament, match, scorer, "scorer"
    )

    assert response.status_code == 201
    assert response.json()["assignment_type"] == "scorer"
    assert response.json()["official_id"] == scorer.id


@pytest.mark.parametrize(
    ("role", "assignment_type"),
    [
        ("player", "referee"),
        ("scorer", "referee"),
        ("official", "scorer"),
    ],
)
def test_assignment_rejects_incompatible_staff_role(
    db, role, assignment_type
):
    organiser = create_user(db, "organiser")
    staff = create_user(db, role)
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    response = assign(
        organiser, tournament, match, staff, assignment_type
    )

    assert response.status_code == 400


def test_assignment_rejects_inactive_staff(db):
    organiser = create_user(db, "organiser")
    referee = create_user(db, "official", is_active=False)
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    response = assign(organiser, tournament, match, referee)

    assert response.status_code == 400


def test_assignment_rejects_duplicate_staff_on_same_match(db):
    organiser = create_user(db, "organiser")
    referee = create_user(db, "official")
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    first = assign(organiser, tournament, match, referee)
    second = assign(organiser, tournament, match, referee)

    assert first.status_code == 201
    assert second.status_code == 409


def test_assignment_rejects_overlapping_match_schedule(db):
    organiser = create_user(db, "organiser")
    referee = create_user(db, "official")
    tournament = create_tournament(db, organiser.id)

    first_match = create_match(
        db,
        tournament.id,
        match_number=1,
        scheduled_at=datetime(
            2099, 1, 2, 10, 0, tzinfo=timezone.utc
        ),
    )
    second_match = create_match(
        db,
        tournament.id,
        match_number=2,
        scheduled_at=datetime(
            2099, 1, 2, 10, 30, tzinfo=timezone.utc
        ),
    )

    first = assign(organiser, tournament, first_match, referee)
    second = assign(organiser, tournament, second_match, referee)

    assert first.status_code == 201
    assert second.status_code == 409


def test_non_organiser_cannot_assign_staff(db):
    organiser = create_user(db, "organiser")
    player = create_user(db, "player")
    referee = create_user(db, "official")
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    response = assign(player, tournament, match, referee)

    assert response.status_code == 403


def test_other_organiser_cannot_assign_staff_to_tournament(db):
    organiser = create_user(db, "organiser")
    other_organiser = create_user(db, "organiser")
    referee = create_user(db, "official")
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    response = assign(other_organiser, tournament, match, referee)

    assert response.status_code == 403


def test_assignment_rejects_match_from_another_tournament(db):
    organiser = create_user(db, "organiser")
    referee = create_user(db, "official")
    tournament_one = create_tournament(db, organiser.id)
    tournament_two = create_tournament(db, organiser.id)
    match = create_match(db, tournament_two.id)

    response = assign(organiser, tournament_one, match, referee)

    assert response.status_code == 404


def test_staff_can_retrieve_only_their_assigned_matches(db):
    organiser = create_user(db, "organiser")
    referee = create_user(db, "official")
    another_referee = create_user(db, "official")
    tournament = create_tournament(db, organiser.id)

    assigned_match = create_match(db, tournament.id, match_number=1)
    other_match = create_match(
        db,
        tournament.id,
        match_number=2,
        scheduled_at=datetime(
            2099, 1, 2, 13, 0, tzinfo=timezone.utc
        ),
    )

    db.add_all(
        [
            OfficialAssignment(
                match_id=assigned_match.id,
                official_id=referee.id,
                assignment_type="referee",
                status="active",
            ),
            OfficialAssignment(
                match_id=other_match.id,
                official_id=another_referee.id,
                assignment_type="referee",
                status="active",
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/official-assignments/my-matches",
        headers=auth_header(referee),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == assigned_match.id
    assert data[0]["assignment_type"] == "referee"


def test_staff_retrieval_excludes_inactive_assignments(db):
    organiser = create_user(db, "organiser")
    referee = create_user(db, "official")
    tournament = create_tournament(db, organiser.id)
    match = create_match(db, tournament.id)

    db.add(
        OfficialAssignment(
            match_id=match.id,
            official_id=referee.id,
            assignment_type="referee",
            status="inactive",
        )
    )
    db.commit()

    response = client.get(
        "/official-assignments/my-matches",
        headers=auth_header(referee),
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "role",
    ["player", "organiser", "spectator"],
)
def test_non_staff_cannot_retrieve_assigned_matches(db, role):
    user = create_user(db, role)

    response = client.get(
        "/official-assignments/my-matches",
        headers=auth_header(user),
    )

    assert response.status_code == 403


def test_assigned_match_retrieval_requires_authentication():
    response = client.get("/official-assignments/my-matches")

    assert response.status_code == 401


def test_inactive_official_cannot_retrieve_assigned_matches(db):
    referee = create_user(db, "official", is_active=False)

    response = client.get(
        "/official-assignments/my-matches",
        headers=auth_header(referee),
    )

    assert response.status_code == 401