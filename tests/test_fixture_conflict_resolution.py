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
        name=f"Conflict Resolution Tournament {uuid.uuid4()}",
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
        name=f"Resolution Team {uuid.uuid4()}",
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


def test_resolve_conflicts_moves_overlapping_match(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    team_c = create_team(db, organizer.id)

    overlapping_time = datetime(
        2099, 1, 2, 10, 0, tzinfo=timezone.utc
    )

    first_match = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        overlapping_time,
    )
    second_match = create_match(
        db,
        tournament.id,
        2,
        team_a.id,
        team_c.id,
        overlapping_time,
    )

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/resolve-conflicts",
        headers=auth_header(organizer),
    )

    assert response.status_code == 200
    assert response.json()["resolved_count"] >= 1

    db.refresh(first_match)
    db.refresh(second_match)

    assert first_match.scheduled_at != second_match.scheduled_at


def test_resolve_conflicts_rejects_tournament_without_fixtures(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/resolve-conflicts",
        headers=auth_header(organizer),
    )

    assert response.status_code == 409


def test_resolve_conflicts_rejects_non_owner(db):
    owner = create_user(db)
    other_organizer = create_user(db)
    tournament = create_tournament(db, owner.id)

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/resolve-conflicts",
        headers=auth_header(other_organizer),
    )

    assert response.status_code == 403


def test_resolve_conflicts_requires_authentication(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    response = client.post(
        f"/matches/tournaments/{tournament.id}/fixtures/resolve-conflicts"
    )

    assert response.status_code == 401


def test_resolve_conflicts_unpublishes_changed_fixtures(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    tournament.fixtures_published = True
    db.commit()

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
        f"/matches/tournaments/{tournament.id}/fixtures/resolve-conflicts",
        headers=auth_header(organizer),
    )

    assert response.status_code == 200

    db.refresh(tournament)
    assert tournament.fixtures_published is False