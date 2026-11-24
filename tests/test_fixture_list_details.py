
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.modules.match.models.match import Match
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User
from app.modules.venue.models.venue import Venue


client = TestClient(app)


def create_user(db):
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


def create_tournament(db, organizer_id):
    tournament = Tournament(
        name=f"Fixture List Test {uuid.uuid4()}",
        format="round_robin",
        start_date=datetime(2099, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 1, 10, 23, 59, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organizer_id,
        fixtures_published=True,
    
        registration_open_at=datetime(2098, 12, 1, 0, 0, tzinfo=timezone.utc),
        registration_close_at=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc))
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


def create_team(db, captain_id):
    team = Team(
        name=f"Fixture Test Team {uuid.uuid4()}",
        captain_id=captain_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def create_venue(db):
    venue = Venue(
        name=f"Fixture Test Venue {uuid.uuid4()}",
        location="Dhaka",
        description="Fixture endpoint test venue",
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
    match_status="scheduled",
):
    match = Match(
        tournament_id=tournament_id,
        match_number=match_number,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        scheduled_at=scheduled_at,
        venue_id=venue_id,
        status=match_status,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def list_url(tournament_id):
    return f"/matches/tournaments/{tournament_id}/fixtures"


def details_url(tournament_id, match_id):
    return (
        f"/matches/tournaments/{tournament_id}"
        f"/fixtures/{match_id}"
    )


def test_list_fixtures_returns_only_requested_tournament(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    another_tournament = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    team_c = create_team(db, organizer.id)
    venue = create_venue(db)

    fixture = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        venue.id,
    )

    create_match(
        db,
        another_tournament.id,
        1,
        team_b.id,
        team_c.id,
        datetime(2099, 1, 3, 10, 0, tzinfo=timezone.utc),
        venue.id,
    )

    response = client.get(list_url(tournament.id))

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == fixture.id
    assert data[0]["tournament_id"] == tournament.id


def test_list_fixtures_filters_by_status(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    team_c = create_team(db, organizer.id)

    scheduled_fixture = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        match_status="scheduled",
    )

    create_match(
        db,
        tournament.id,
        2,
        team_b.id,
        team_c.id,
        datetime(2099, 1, 3, 10, 0, tzinfo=timezone.utc),
        match_status="completed",
    )

    response = client.get(
        list_url(tournament.id),
        params={"status": "scheduled"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == scheduled_fixture.id
    assert data[0]["status"] == "scheduled"


def test_list_fixtures_filters_by_team(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    team_c = create_team(db, organizer.id)

    matching_fixture = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    create_match(
        db,
        tournament.id,
        2,
        team_b.id,
        team_c.id,
        datetime(2099, 1, 3, 10, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        list_url(tournament.id),
        params={"team_id": team_a.id},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == matching_fixture.id


def test_list_fixtures_filters_by_venue_and_date_range(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    team_c = create_team(db, organizer.id)
    team_d = create_team(db, organizer.id)
    venue_a = create_venue(db)
    venue_b = create_venue(db)

    matching_fixture = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 3, 10, 0, tzinfo=timezone.utc),
        venue_a.id,
    )

    create_match(
        db,
        tournament.id,
        2,
        team_c.id,
        team_d.id,
        datetime(2099, 1, 5, 10, 0, tzinfo=timezone.utc),
        venue_b.id,
    )

    response = client.get(
        list_url(tournament.id),
        params={
            "venue_id": venue_a.id,
            "start_at": "2099-01-02T00:00:00Z",
            "end_at": "2099-01-04T23:59:59Z",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == matching_fixture.id
    assert data[0]["venue_id"] == venue_a.id


def test_list_fixtures_rejects_invalid_date_range(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    response = client.get(
        list_url(tournament.id),
        params={
            "start_at": "2099-01-05T00:00:00Z",
            "end_at": "2099-01-02T00:00:00Z",
        },
    )

    assert response.status_code == 400


def test_list_fixtures_returns_404_for_unknown_tournament(db):
    response = client.get(list_url(999999999))

    assert response.status_code == 404


def test_fixture_details_returns_correct_fixture(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)
    venue = create_venue(db)

    fixture = create_match(
        db,
        tournament.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
        venue.id,
    )

    response = client.get(
        details_url(tournament.id, fixture.id)
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == fixture.id
    assert data["tournament_id"] == tournament.id
    assert data["match_number"] == 1
    assert data["team_a_id"] == team_a.id
    assert data["team_b_id"] == team_b.id
    assert data["venue_id"] == venue.id
    assert data["status"] == "scheduled"
    assert "scheduled_at" in data
    assert "round_id" in data


def test_fixture_details_returns_404_for_unknown_fixture(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)

    response = client.get(
        details_url(tournament.id, 999999999)
    )

    assert response.status_code == 404


def test_fixture_details_does_not_expose_another_tournaments_fixture(db):
    organizer = create_user(db)
    tournament_a = create_tournament(db, organizer.id)
    tournament_b = create_tournament(db, organizer.id)

    team_a = create_team(db, organizer.id)
    team_b = create_team(db, organizer.id)

    fixture = create_match(
        db,
        tournament_a.id,
        1,
        team_a.id,
        team_b.id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        details_url(tournament_b.id, fixture.id)
    )

    assert response.status_code == 404

def _bearer(user):
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _unpublished_tournament_with_fixture(db):
    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    tournament.fixtures_published = False
    db.commit()

    fixture = create_match(
        db,
        tournament.id,
        1,
        create_team(db, organizer.id).id,
        create_team(db, organizer.id).id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )
    return organizer, tournament, fixture


def test_unpublished_fixtures_are_hidden_from_anonymous_callers(db):
    _, tournament, fixture = _unpublished_tournament_with_fixture(db)

    assert client.get(list_url(tournament.id)).status_code == 404
    assert client.get(details_url(tournament.id, fixture.id)).status_code == 404


def test_unpublished_fixtures_are_hidden_from_other_organisers(db):
    _, tournament, fixture = _unpublished_tournament_with_fixture(db)
    other = create_user(db)

    response = client.get(list_url(tournament.id), headers=_bearer(other))

    assert response.status_code == 404


def test_owner_can_see_unpublished_fixtures(db):
    organizer, tournament, fixture = _unpublished_tournament_with_fixture(db)

    listing = client.get(list_url(tournament.id), headers=_bearer(organizer))
    details = client.get(
        details_url(tournament.id, fixture.id), headers=_bearer(organizer)
    )

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [fixture.id]
    assert details.status_code == 200


def test_fixture_list_shows_only_verified_scores(db):
    from app.modules.score.models.score import Score

    organizer = create_user(db)
    tournament = create_tournament(db, organizer.id)
    verified = create_match(
        db, tournament.id, 1,
        create_team(db, organizer.id).id, create_team(db, organizer.id).id,
        datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
    )
    pending = create_match(
        db, tournament.id, 2,
        create_team(db, organizer.id).id, create_team(db, organizer.id).id,
        datetime(2099, 1, 2, 12, 0, tzinfo=timezone.utc),
    )
    db.add_all([
        Score(match_id=verified.id, team_a_score=3, team_b_score=1,
              is_verified=True, verification_status="verified"),
        Score(match_id=pending.id, team_a_score=5, team_b_score=0),
    ])
    db.commit()

    rows = {row["id"]: row for row in client.get(list_url(tournament.id)).json()}

    assert (rows[verified.id]["team_a_score"], rows[verified.id]["team_b_score"]) == (3, 1)
    assert rows[pending.id]["team_a_score"] is None
    assert rows[pending.id]["team_b_score"] is None
