import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.modules.score.models.score import Score, ScoreVerificationStatus
from app.modules.player_team.models.player import Player
from app.modules.tournament_team.models.tournament_team import TournamentTeam

client = TestClient(app)


def make_user(db):
    user = User(
        email=f"{uuid.uuid4()}@test.com",
        password_hash="test-password-hash",
        role="organiser",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_tournament(db, organizer_id, published=False, tournament_status="upcoming"):
    tournament = Tournament(
        name=f"Public API Test {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, tzinfo=timezone.utc),
        status=tournament_status,
        fixtures_published=published,
        organizer_id=organizer_id,
    
        registration_open_at=datetime(2098, 12, 1, 0, 0, tzinfo=timezone.utc),
        registration_close_at=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc))
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def make_team(db, captain_id):
    team = Team(
        name=f"Public API Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def make_match(db, tournament_id, team_a_id, team_b_id):
    match = Match(
        tournament_id=tournament_id,
        match_number=1,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        scheduled_at=datetime(
            2099, 1, 2, 10, 0, tzinfo=timezone.utc
        ),
        status="completed",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def test_public_tournament_details(db):
    organizer = make_user(db)
    tournament = make_tournament(db, organizer.id)

    response = client.get(
        f"/spectator/tournaments/{tournament.id}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == tournament.id
    assert response.json()["name"] == tournament.name


def test_public_tournament_details_returns_404_for_unknown_tournament(db):
    response = client.get("/spectator/tournaments/999999999")

    assert response.status_code == 404


def test_public_fixtures_are_available_after_publication(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db,
        organizer.id,
        published=True,
    )
    team_a = make_team(db, organizer.id)
    team_b = make_team(db, organizer.id)

    match = make_match(
        db,
        tournament.id,
        team_a.id,
        team_b.id,
    )

    response = client.get(
        f"/spectator/tournaments/{tournament.id}/fixtures"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == match.id


def test_public_fixtures_are_hidden_before_publication(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db,
        organizer.id,
        published=False,
    )

    response = client.get(
        f"/spectator/tournaments/{tournament.id}/fixtures"
    )

    assert response.status_code == 404


def test_public_result_returns_finalized_result(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db,
        organizer.id,
        published=True,
    )
    team_a = make_team(db, organizer.id)
    team_b = make_team(db, organizer.id)
    match = make_match(
        db,
        tournament.id,
        team_a.id,
        team_b.id,
    )
    score = Score(
        match_id=match.id,
        team_a_score=3,
        team_b_score=1,
        is_verified=True,
        verification_status=ScoreVerificationStatus.VERIFIED.value,
    )
    db.add(score)
    db.flush()
    result = MatchResult(
        match_id=match.id,
        outcome="team_a_win",
        winner_team_id=team_a.id,
        loser_team_id=team_b.id,
        team_a_score=3,
        team_b_score=1,
        finalized_by_id=organizer.id,
        finalized_at=datetime.now(timezone.utc),
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    response = client.get(
        f"/spectator/matches/{match.id}/result"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["match_id"] == match.id
    assert data["outcome"] == "team_a_win"
    assert data["team_a_score"] == 3
    assert data["team_b_score"] == 1


def test_public_result_returns_404_when_not_finalized(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db,
        organizer.id,
        published=True,
    )
    team_a = make_team(db, organizer.id)
    team_b = make_team(db, organizer.id)
    match = make_match(
        db,
        tournament.id,
        team_a.id,
        team_b.id,
    )

    response = client.get(
        f"/spectator/matches/{match.id}/result"
    )

    assert response.status_code == 404


def test_public_result_is_hidden_before_fixture_publication(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db,
        organizer.id,
        published=False,
    )
    team_a = make_team(db, organizer.id)
    team_b = make_team(db, organizer.id)
    match = make_match(
        db,
        tournament.id,
        team_a.id,
        team_b.id,
    )

    result = MatchResult(
        match_id=match.id,
        outcome="team_a_win",
        winner_team_id=team_a.id,
        loser_team_id=team_b.id,
        team_a_score=2,
        team_b_score=0,
        finalized_by_id=organizer.id,
        finalized_at=datetime.now(timezone.utc),
    )
    db.add(result)
    db.commit()

    response = client.get(
        f"/spectator/matches/{match.id}/result"
    )

    assert response.status_code == 404

def test_public_match_history_returns_matches_in_order(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db,
        organizer.id,
        published=True,
    )
    team_a = make_team(db, organizer.id)
    team_b = make_team(db, organizer.id)

    first_match = make_match(
        db,
        tournament.id,
        team_a.id,
        team_b.id,
    )

    second_match = Match(
        tournament_id=tournament.id,
        match_number=2,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        scheduled_at=datetime(
            2099, 1, 3, 10, 0, tzinfo=timezone.utc
        ),
        status="completed",
    )
    db.add(second_match)
    db.commit()
    db.refresh(second_match)

    response = client.get(
        f"/spectator/tournaments/{tournament.id}/history"
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [
        first_match.id,
        second_match.id,
    ]
    assert data[0]["result"] is None


def test_public_match_history_hidden_before_publication(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db,
        organizer.id,
        published=False,
    )

    response = client.get(
        f"/spectator/tournaments/{tournament.id}/history"
    )

    assert response.status_code == 404

def test_public_team_information_returns_roster_and_tournaments(db):
    organizer = make_user(db)
    tournament = make_tournament(db, organizer.id, published=True)
    team = make_team(db, organizer.id)

    db.add(
        TournamentTeam(
            tournament_id=tournament.id,
            team_id=team.id,
        )
    )

    player = Player(
        user_id=make_user(db).id,
        team_id=team.id,
        first_name="Public",
        last_name="Player",
        status="active",
    )
    db.add(player)
    db.commit()

    response = client.get(f"/spectator/teams/{team.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == team.id
    assert data["name"] == team.name
    assert data["roster"][0]["first_name"] == "Public"
    assert data["tournaments"][0]["id"] == tournament.id
    assert "captain_id" not in data
    assert "user_id" not in data["roster"][0]


def test_public_team_information_returns_404_for_unknown_team(db):
    response = client.get("/spectator/teams/999999999")

    assert response.status_code == 404


def test_public_player_information_returns_public_profile(db):
    organizer = make_user(db)
    tournament = make_tournament(db, organizer.id, published=True)
    team = make_team(db, organizer.id)

    db.add(
        TournamentTeam(
            tournament_id=tournament.id,
            team_id=team.id,
        )
    )

    player_user = make_user(db)
    player = Player(
        user_id=player_user.id,
        team_id=team.id,
        first_name="Searchable",
        last_name="Player",
        status="active",
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    response = client.get(f"/spectator/players/{player.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == player.id
    assert data["first_name"] == "Searchable"
    assert data["team"]["id"] == team.id
    assert data["tournaments"][0]["id"] == tournament.id
    assert data["performance"]["played"] == 0
    assert "user_id" not in data


def test_public_player_information_returns_404_for_unknown_player(db):
    response = client.get("/spectator/players/999999999")

    assert response.status_code == 404


def test_public_search_finds_published_tournament(db):
    organizer = make_user(db)
    tournament = make_tournament(db, organizer.id, published=True)

    response = client.get(
        "/spectator/search",
        params={"q": tournament.name, "category": "tournaments"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "tournaments"
    assert data["results"]["tournaments"]["total"] == 1
    assert data["results"]["tournaments"]["items"][0]["id"] == tournament.id


def test_public_search_rejects_whitespace_query(db):
    response = client.get(
        "/spectator/search",
        params={"q": "   "},
    )

    assert response.status_code == 422


def test_public_search_rejects_invalid_category(db):
    response = client.get(
        "/spectator/search",
        params={"q": "test", "category": "users"},
    )

    assert response.status_code == 422


def test_unverified_score_result_is_not_public(db):
    organizer = make_user(db)
    tournament = make_tournament(db, organizer.id, published=True)
    team_a = make_team(db, organizer.id)
    team_b = make_team(db, organizer.id)
    match = make_match(db, tournament.id, team_a.id, team_b.id)

    score = Score(
        match_id=match.id,
        team_a_score=3,
        team_b_score=1,
        is_verified=False,
        verification_status=ScoreVerificationStatus.PENDING.value,
    )
    result = MatchResult(
        match_id=match.id,
        outcome="team_a_win",
        winner_team_id=team_a.id,
        loser_team_id=team_b.id,
        team_a_score=3,
        team_b_score=1,
        finalized_by_id=organizer.id,
        finalized_at=datetime.now(timezone.utc),
    )
    db.add_all([score, result])
    db.commit()

    response = client.get(f"/spectator/matches/{match.id}/result")

    assert response.status_code == 404

def test_archived_tournament_details_return_404(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db, organizer.id, published=True, tournament_status="archived"
    )

    response = client.get(f"/spectator/tournaments/{tournament.id}")

    assert response.status_code == 404


def test_archived_tournament_fixtures_return_404(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db, organizer.id, published=True, tournament_status="archived"
    )

    response = client.get(
        f"/spectator/tournaments/{tournament.id}/fixtures"
    )

    assert response.status_code == 404


def test_archived_tournament_history_returns_404(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db, organizer.id, published=True, tournament_status="archived"
    )

    response = client.get(
        f"/spectator/tournaments/{tournament.id}/history"
    )

    assert response.status_code == 404


def test_archived_tournament_match_result_is_not_public(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db, organizer.id, published=True, tournament_status="archived"
    )
    team_a = make_team(db, organizer.id)
    team_b = make_team(db, organizer.id)
    match = make_match(db, tournament.id, team_a.id, team_b.id)

    score = Score(
        match_id=match.id,
        team_a_score=3,
        team_b_score=1,
        is_verified=True,
        verification_status=ScoreVerificationStatus.VERIFIED.value,
    )
    result = MatchResult(
        match_id=match.id,
        outcome="team_a_win",
        winner_team_id=team_a.id,
        loser_team_id=team_b.id,
        team_a_score=3,
        team_b_score=1,
        finalized_by_id=organizer.id,
        finalized_at=datetime.now(timezone.utc),
    )
    db.add_all([score, result])
    db.commit()

    response = client.get(f"/spectator/matches/{match.id}/result")

    assert response.status_code == 404


def test_archived_tournament_is_excluded_from_public_search(db):
    organizer = make_user(db)
    tournament = make_tournament(
        db, organizer.id, published=True, tournament_status="archived"
    )

    response = client.get(
        "/spectator/search",
        params={"q": tournament.name, "category": "tournaments"},
    )

    assert response.status_code == 200
    assert response.json()["results"]["tournaments"]["total"] == 0


def test_team_and_player_profiles_hide_archived_tournament_history(db):
    organizer = make_user(db)

    archived = make_tournament(
        db, organizer.id, published=True, tournament_status="archived"
    )
    active = make_tournament(
        db, organizer.id, published=True, tournament_status="upcoming"
    )

    team = make_team(db, organizer.id)

    db.add_all([
        TournamentTeam(tournament_id=archived.id, team_id=team.id),
        TournamentTeam(tournament_id=active.id, team_id=team.id),
    ])

    player_user = make_user(db)
    player = Player(
        user_id=player_user.id,
        team_id=team.id,
        first_name="Archived",
        last_name="Player",
        status="active",
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    team_response = client.get(f"/spectator/teams/{team.id}")
    player_response = client.get(f"/spectator/players/{player.id}")

    assert team_response.status_code == 200
    team_tournament_ids = {
        item["id"] for item in team_response.json()["tournaments"]
    }
    assert active.id in team_tournament_ids
    assert archived.id not in team_tournament_ids

    assert player_response.status_code == 200
    player_tournament_ids = {
        item["id"] for item in player_response.json()["tournaments"]
    }
    assert active.id in player_tournament_ids
    assert archived.id not in player_tournament_ids
