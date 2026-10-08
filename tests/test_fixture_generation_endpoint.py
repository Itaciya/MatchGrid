import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import (
    RegistrationStatus,
    RegistrationType,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.modules.venue.models.venue import Venue


client = TestClient(app)


def create_user(db, role="captain"):
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


def create_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"Endpoint Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(
            2099, 1, 1, 10, 0, tzinfo=timezone.utc
        ),
        end_date=datetime(
            2099, 1, 10, 18, 0, tzinfo=timezone.utc
        ),
        status="upcoming",
        organizer_id=organizer_id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def create_team(db, captain_id):
    team = Team(
        name=f"Endpoint Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def create_venue(db):
    venue = Venue(
        name=f"Endpoint Venue {uuid.uuid4()}",
        location="Dhaka",
        description="Test venue",
        capacity=5000,
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def approve_team_registration(db, tournament_id, team_id):
    registration = Registration(
        tournament_id=tournament_id,
        team_id=team_id,
        player_id=None,
        registration_type=RegistrationType.TEAM.value,
        status=RegistrationStatus.APPROVED.value,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return registration


def auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_authorized_organizer_can_generate_fixtures(db):
    organizer = create_user(db, role="organiser")
    tournament = create_tournament(db, organizer.id)
    venue = create_venue(db)

    teams = [
        create_team(db, organizer.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/generate",
        json={
            "tournament_id": tournament.id,
            "team_ids": [team.id for team in teams],
            "venue_id": venue.id,
            "fixture_date": "2099-01-02",
            "fixture_time": "10:00:00",
        },
        headers=auth_header(organizer),
    )

    assert response.status_code == 201

    data = response.json()

    assert len(data) == 6
    assert all(item["tournament_id"] == tournament.id for item in data)
    assert all(item["status"] == "scheduled" for item in data)
    assert all(item["venue_id"] == venue.id for item in data)


def test_non_owner_organizer_cannot_generate_fixtures(db):
    owner = create_user(db, role="organiser")
    other_organizer = create_user(db, role="organiser")

    tournament = create_tournament(db, owner.id)
    venue = create_venue(db)

    teams = [
        create_team(db, owner.id)
        for _ in range(2)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/generate",
        json={
            "tournament_id": tournament.id,
            "team_ids": [team.id for team in teams],
            "venue_id": venue.id,
            "fixture_date": "2099-01-02",
            "fixture_time": "10:00:00",
        },
        headers=auth_header(other_organizer),
    )

    assert response.status_code == 403


def test_unauthorized_user_cannot_generate_fixtures(db):
    organizer = create_user(db, role="organiser")
    tournament = create_tournament(db, organizer.id)
    venue = create_venue(db)

    teams = [
        create_team(db, organizer.id)
        for _ in range(2)
    ]

    for team in teams:
        approve_team_registration(
            db,
            tournament.id,
            team.id,
        )

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/generate",
        json={
            "tournament_id": tournament.id,
            "team_ids": [team.id for team in teams],
            "venue_id": venue.id,
            "fixture_date": "2099-01-02",
            "fixture_time": "10:00:00",
        },
    )

    assert response.status_code == 401


def test_invalid_fixture_input_is_rejected(db):
    organizer = create_user(db, role="organiser")
    tournament = create_tournament(db, organizer.id)
    venue = create_venue(db)

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/generate",
        json={
            "tournament_id": tournament.id,
            "team_ids": [1, 1],
            "venue_id": venue.id,
            "fixture_date": "2099-01-02",
            "fixture_time": "10:00:00",
        },
        headers=auth_header(organizer),
    )

    assert response.status_code == 422