import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.modules.venue.models.venue import Venue


client = TestClient(app)


def create_user(db, role="organiser"):
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
        name=f"Fixture Update Tournament {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 18, 0, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def create_team(db, captain_id):
    team = Team(
        name=f"Update Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def create_venue(db):
    venue = Venue(
        name=f"Update Venue {uuid.uuid4()}",
        location="Dhaka",
        description="Fixture update test venue",
        capacity=100,
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def create_match(
    db,
    tournament_id,
    match_number,
    team_a_id,
    team_b_id,
    scheduled_at,
    venue_id=None,
):
    match = Match(
        tournament_id=tournament_id,
        match_number=match_number,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        venue_id=venue_id,
        scheduled_at=scheduled_at,
        status="scheduled",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def auth_header(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def update_url(tournament_id, match_id):
    return (
        f"/matches/tournaments/{tournament_id}"
        f"/fixtures/{match_id}"
    )


def test_update_fixture_schedule_successfully(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)

    match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.patch(
        update_url(tournament.id, match.id),
        headers=auth_header(organizer),
        json={"scheduled_at": "2099-01-02T11:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == match.id

    db.refresh(match)
    assert match.scheduled_at == datetime(
        2099, 1, 2, 11, 0, tzinfo=timezone.utc
    )


def test_update_fixture_rejects_team_conflict(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    team_c = create_team(db, organizer.id)

    original_time = datetime(
        2099, 1, 2, 10, 0, tzinfo=timezone.utc
    )

    match_to_update = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 11, 0, tzinfo=timezone.utc),
    )

    create_match(
        db,
        tournament.id,
        2,
        team_a.id,
        team_c.id,
        original_time,
    )

    response = client.patch(
        update_url(tournament.id, match_to_update.id),
        headers=auth_header(organizer),
        json={"scheduled_at": "2099-01-02T10:00:00Z"},
    )

    assert response.status_code == 409

    db.refresh(match_to_update)
    assert match_to_update.scheduled_at == datetime(
        2099, 1, 2, 11, 0, tzinfo=timezone.utc
    )


def test_update_fixture_rejects_invalid_venue(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)

    match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.patch(
        update_url(tournament.id, match.id),
        headers=auth_header(organizer),
        json={"venue_id": 999999999},
    )

    assert response.status_code == 404


def test_update_fixture_rejects_schedule_outside_tournament_dates(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)

    match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.patch(
        update_url(tournament.id, match.id),
        headers=auth_header(organizer),
        json={"scheduled_at": "2099-01-10T18:00:00Z"},
    )

    assert response.status_code == 400


def test_update_fixture_unpublishes_changed_fixtures(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)

    match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    tournament.fixtures_published = True
    db.commit()

    response = client.patch(
        update_url(tournament.id, match.id),
        headers=auth_header(organizer),
        json={"scheduled_at": "2099-01-02T11:00:00Z"},
    )

    assert response.status_code == 200

    db.refresh(tournament)
    assert tournament.fixtures_published is False


def test_update_fixture_rejects_non_owner(db):
    owner = create_user(db)
    other_organizer = create_user(db)

    tournament = create_tournament(db, owner.id)
    team_a = create_team(db, owner.id)
    team_b = create_team(db, owner.id)

    match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.patch(
        update_url(tournament.id, match.id),
        headers=auth_header(other_organizer),
        json={"scheduled_at": "2099-01-02T11:00:00Z"},
    )

    assert response.status_code == 403


def test_update_fixture_requires_authentication(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)

    match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.patch(
        update_url(tournament.id, match.id),
        json={"scheduled_at": "2099-01-02T11:00:00Z"},
    )

    assert response.status_code == 401


def test_update_fixture_accepts_valid_venue(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    venue = create_venue(db)

    match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.patch(
        update_url(tournament.id, match.id),
        headers=auth_header(organizer),
        json={"venue_id": venue.id},
    )

    assert response.status_code == 200

    db.refresh(match)
    assert match.venue_id == venue.id