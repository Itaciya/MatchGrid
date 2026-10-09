
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

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
        name=f"Publication Tournament {uuid.uuid4()}",
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
        name=f"Publication Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def create_match(
    db,
    tournament_id,
    match_number,
    team_a_id,
    team_b_id,
    scheduled_at,
):
    match = Match(
        tournament_id=tournament_id,
        match_number=match_number,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        venue_id=None,
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


def test_publish_fixtures_successfully(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)

    create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/publish",
        headers=auth_header(organizer),
    )

    assert response.status_code == 200
    assert response.json()["fixtures_published"] is True

    db.refresh(tournament)
    assert tournament.fixtures_published is True


def test_publish_rejects_tournament_without_fixtures(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/publish",
        headers=auth_header(organizer),
    )

    assert response.status_code == 400

    db.refresh(tournament)
    assert tournament.fixtures_published is False



def test_publish_rejects_conflicting_fixtures(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    team_c = create_team(db, organizer.id)

    overlapping_time = datetime(
        2099, 1, 2, 10, 0, tzinfo=timezone.utc
    )

    create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        overlapping_time,
    )

    create_match(
        db,
        tournament.id,
        2,
        team_a.id,
        team_c.id,
        overlapping_time,
    )

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/publish",
        headers=auth_header(organizer),
    )

    # Conflicting fixtures must not be published.
    assert response.status_code == 409

    # The tournament must remain unpublished.
    db.refresh(tournament)
    assert tournament.fixtures_published is False

def test_non_owner_organizer_cannot_publish_fixtures(db):
    owner = create_user(db)
    other_organizer = create_user(db)
    tournament = create_tournament(db, owner.id)

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/publish",
        headers=auth_header(other_organizer),
    )

    assert response.status_code == 403

    db.refresh(tournament)
    assert tournament.fixtures_published is False


def test_unauthenticated_user_cannot_publish_fixtures(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/publish"
    )

    assert response.status_code == 401

    db.refresh(tournament)
    assert tournament.fixtures_published is False