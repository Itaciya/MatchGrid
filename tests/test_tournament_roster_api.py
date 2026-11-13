from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import quote

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.modules.user.models import User
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.registration.models.registration import Registration
from app.modules.tournament_team.models.tournament_team import TournamentTeam
from app.modules.tournament_team.models.tournament_team_player import TournamentTeamPlayer

client = TestClient(app)


def _make_user(db, role):
    user = User(
        email=f"roster_test_{uuid4()}@example.com",
        password_hash="test_password_hash",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _headers(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _make_roster_context(db, min_size=1, max_size=2):
    organizer = _make_user(db, "organiser")
    captain = _make_user(db, "captain")

    team = Team(
        name=f"Roster Test Team {uuid4()}",
        captain_id=captain.id,
        status="active",
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    tournament = Tournament(
        name=f"Roster Test Tournament {uuid4()}",
        category="sports",
        participation_type="team",
        min_roster_size=min_size,
        max_roster_size=max_size,
        description="Roster API automated test",
        format="knockout",
        status="upcoming",
        fixtures_published=False,
        organizer_id=organizer.id,
        start_date=datetime(2099, 6, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 6, 10, tzinfo=timezone.utc),
        registration_open_at=datetime.now(timezone.utc) - timedelta(days=1),
        registration_close_at=datetime(2099, 5, 31, tzinfo=timezone.utc),
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    registration = Registration(
        tournament_id=tournament.id,
        team_id=team.id,
        registration_type="team",
        status="approved",
    )
    db.add(registration)

    association = TournamentTeam(
        tournament_id=tournament.id,
        team_id=team.id,
    )
    db.add(association)
    db.commit()

    return organizer, captain, team, tournament


def _make_player(db, first_name="Test", last_name="Player"):
    user = _make_user(db, "player")

    player = Player(
        user_id=user.id,
        team_id=None,
        first_name=first_name,
        last_name=last_name,
        status="active",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def test_captain_roster_search_add_remove_and_fixture_lock(db):
    _, captain, team, tournament = _make_roster_context(db)
    player_one = _make_player(db, "Alpha", "RosterTest")
    player_two = _make_player(db, "Beta", "RosterTest")

    base = (
        f"/tournament-rosters/{tournament.id}"
        f"/teams/{team.id}"
    )
    headers = _headers(captain)

    response = client.get(base, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == []

    response = client.get(
        f"{base}/search?q={quote('Alpha RosterTest')}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert any(
        item["player_id"] == player_one.id
        for item in response.json()
    )

    response = client.get(
        f"{base}/search?q={player_one.user_id}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert any(
        item["player_id"] == player_one.id
        for item in response.json()
    )

    response = client.post(
        base,
        headers=headers,
        json={"player_id": player_one.id},
    )
    assert response.status_code == 201, response.text

    response = client.post(
        base,
        headers=headers,
        json={"player_id": player_one.id},
    )
    assert response.status_code == 409

    response = client.post(
        base,
        headers=headers,
        json={"player_id": player_two.id},
    )
    assert response.status_code == 201, response.text

    response = client.delete(
        f"{base}/{player_one.id}",
        headers=headers,
    )
    assert response.status_code == 204

    response = client.delete(
        f"{base}/{player_two.id}",
        headers=headers,
    )
    assert response.status_code == 409

    db.query(Tournament).filter(
        Tournament.id == tournament.id
    ).update({"fixtures_published": True})
    db.commit()

    response = client.get(base, headers=headers)
    assert response.status_code == 200

    response = client.post(
        base,
        headers=headers,
        json={"player_id": player_one.id},
    )
    assert response.status_code == 409


def test_other_captain_cannot_access_another_team_roster(db):
    _, captain, team, tournament = _make_roster_context(db)
    other_captain = _make_user(db, "captain")
    player = _make_player(db)

    base = (
        f"/tournament-rosters/{tournament.id}"
        f"/teams/{team.id}"
    )
    headers = _headers(other_captain)

    response = client.get(base, headers=headers)
    assert response.status_code == 403

    response = client.get(
        f"{base}/search?q=Test",
        headers=headers,
    )
    assert response.status_code == 403

    response = client.post(
        base,
        headers=headers,
        json={"player_id": player.id},
    )
    assert response.status_code == 403


def test_ordinary_player_cannot_modify_another_teams_roster(db):
    _, captain, team, tournament = _make_roster_context(db)
    ordinary_player = _make_user(db, "player")
    target = _make_player(db)

    base = (
        f"/tournament-rosters/{tournament.id}"
        f"/teams/{team.id}"
    )
    headers = _headers(ordinary_player)

    response = client.get(base, headers=headers)
    assert response.status_code == 403

    response = client.post(
        base,
        headers=headers,
        json={"player_id": target.id},
    )
    assert response.status_code == 403


def test_roster_search_rejects_empty_query(db):
    _, captain, team, tournament = _make_roster_context(db)

    base = (
        f"/tournament-rosters/{tournament.id}"
        f"/teams/{team.id}"
    )

    response = client.get(
        f"{base}/search?q=",
        headers=_headers(captain),
    )

    assert response.status_code == 422
