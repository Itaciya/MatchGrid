import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.modules.venue.models.venue import Venue


client = TestClient(app)


def create_organizer(db):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash=hash_password("password123"),
        role="organiser",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_captain(db):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash=hash_password("password123"),
        role="captain",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"Regeneration Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(
            2099,
            1,
            1,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        end_date=datetime(
            2099,
            1,
            10,
            18,
            0,
            tzinfo=timezone.utc,
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
        name=f"Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )

    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def create_venue(db):
    venue = Venue(
        name=f"Regeneration Venue {uuid.uuid4()}",
        location="Dhaka",
        description="Test venue",
        capacity=5000,
    )

    db.add(venue)
    db.commit()
    db.refresh(venue)

    return venue


def approve_registration(db, tournament_id, team_id):
    registration = Registration(
        tournament_id=tournament_id,
        team_id=team_id,
        player_id=None,
        registration_type="team",
        status="approved",
    )

    db.add(registration)
    db.commit()


def auth_header(user):
    token = create_access_token(
        user.id,
        user.role,
    )

    return {
        "Authorization": f"Bearer {token}"
    }


def test_regenerate_fixture_endpoint_success(db):
    organizer = create_organizer(db)

    captain = create_captain(db)

    tournament = create_tournament(
        db,
        organizer.id,
    )

    venue = create_venue(db)

    teams = [
        create_team(db, captain.id)
        for _ in range(4)
    ]

    for team in teams:
        approve_registration(
            db,
            tournament.id,
            team.id,
        )

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/regenerate",
        json={
            "tournament_id": tournament.id,
            "team_ids": [
                team.id
                for team in teams
            ],
            "venue_id": venue.id,
            "fixture_date": "2099-01-02",
            "fixture_time": "10:00:00",
        },
        headers=auth_header(organizer),
    )

    assert response.status_code == 200
    assert len(response.json()) == 6

    assert all(
        fixture["venue_id"] == venue.id
        for fixture in response.json()
    )


def test_regenerate_fixture_endpoint_without_permission(db):
    organizer = create_organizer(db)

    venue = create_venue(db)

    response = client.post(
        "/matches/tournaments/999/fixtures/regenerate",
        json={
            "tournament_id": 999,
            "team_ids": [1, 2],
            "venue_id": venue.id,
            "fixture_date": "2099-01-02",
            "fixture_time": "10:00:00",
        },
        headers=auth_header(organizer),
    )

    assert response.status_code in [
        401,
        403,
        404,
    ]