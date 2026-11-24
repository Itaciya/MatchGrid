from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.user.models import User

client = TestClient(app)


def _user(db, role="player"):
    user = User(
        email=f"player_search_{uuid4()}@example.com",
        password_hash="not-used",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _player(db, first_name, last_name, team_id=None, status="active"):
    player = Player(
        user_id=_user(db).id,
        first_name=first_name,
        last_name=last_name,
        team_id=team_id,
        status=status,
    )
    db.add(player)
    db.commit()
    return player


def test_search_finds_players_by_full_name_with_team_name(db):
    marker = uuid4().hex[:8]
    captain = _user(db)
    team = Team(name=f"Search Team {marker}", captain_id=captain.id, status=TeamStatus.ACTIVE)
    db.add(team)
    db.commit()
    free = _player(db, "Rahim", f"Free{marker}")
    signed = _player(db, "Karim", f"Free{marker}", team_id=team.id)

    response = client.get(
        f"/player-team/players/search?q=free{marker}",
        headers=_headers(captain),
    )

    assert response.status_code == 200
    results = {item["id"]: item for item in response.json()}
    assert set(results) == {free.id, signed.id}
    assert results[signed.id]["team_name"] == team.name
    assert results[free.id]["team_name"] is None


def test_available_only_excludes_players_with_a_team(db):
    marker = uuid4().hex[:8]
    captain = _user(db)
    team = Team(name=f"Avail Team {marker}", captain_id=captain.id, status=TeamStatus.ACTIVE)
    db.add(team)
    db.commit()
    free = _player(db, "Nadia", f"Avail{marker}")
    _player(db, "Sadia", f"Avail{marker}", team_id=team.id)
    _player(db, "Inactive", f"Avail{marker}", status="inactive")

    response = client.get(
        f"/player-team/players/search?q=avail{marker}&available_only=true",
        headers=_headers(captain),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [free.id]


def test_like_wildcards_are_matched_literally(db):
    _player(db, "Wild", f"Card{uuid4().hex[:8]}")

    response = client.get(
        "/player-team/players/search?q=%25%25",
        headers=_headers(_user(db)),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_search_requires_login_and_two_characters(db):
    assert client.get("/player-team/players/search?q=ab").status_code == 401
    short = client.get(
        "/player-team/players/search?q=a",
        headers=_headers(_user(db)),
    )
    assert short.status_code == 422
