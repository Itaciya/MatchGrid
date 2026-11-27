"""Role-based notifications across the tournament workflow, their links,
following tournaments, and live delivery after commit."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.modules.notification.models.notification import Notification
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

client = TestClient(app)


def _user(db, role):
    user = User(
        email=f"live_note_{uuid4()}@example.com",
        password_hash="not-used",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _notifications(db, user, kind=None):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if kind:
        query = query.filter(Notification.notification_type == kind)
    db.expire_all()
    return query.order_by(Notification.id).all()


def _league(db):
    """Organiser, scorer, two captains with registered teams, one follower."""
    organiser = _user(db, "organiser")
    scorer = _user(db, "scorer")
    follower = _user(db, "spectator")
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    response = client.post("/organiser/tournaments", headers=_headers(organiser), json={
        "name": f"Live League {uuid4().hex[:6]}", "format": "round_robin",
        "format_config": {"number_of_teams": 2}, "participation_type": "team",
        "min_roster_size": 1, "max_roster_size": 11,
        "registration_open_at": (now - timedelta(days=1)).isoformat(),
        "registration_close_at": (now + timedelta(minutes=30)).isoformat(),
        "start_date": start.isoformat(), "end_date": (start + timedelta(days=3)).isoformat(),
    })
    assert response.status_code == 201, response.text
    tournament_id = response.json()["id"]

    assert client.post(f"/tournaments/{tournament_id}/follow", headers=_headers(follower)).status_code == 200

    captains, registrations = [], []
    for first in ("Arif", "Mahin"):
        captain = _user(db, "player")
        headers = _headers(captain)
        client.post("/player-team/profile", headers=headers, json={"first_name": first, "last_name": "Live"})
        team = client.post("/player-team/team", headers=headers, json={"name": f"{first} FC {uuid4().hex[:6]}"}).json()
        registration = client.post("/registrations/", headers=headers, json={
            "tournament_id": tournament_id, "team_id": team["id"], "registration_type": "team",
        })
        assert registration.status_code == 201, registration.text
        captains.append((captain, team))
        registrations.append(registration.json())

    return organiser, scorer, follower, tournament_id, captains, registrations


def _publish_and_play(db, organiser, scorer, tournament_id, registrations, score=(2, 1)):
    for registration in registrations:
        client.patch(f"/registrations/{registration['id']}/approve", headers=_headers(organiser))
    fixtures = client.post(
        f"/matches/tournaments/{tournament_id}/fixtures/auto-generate", headers=_headers(organiser)
    ).json()
    client.post(f"/official-assignments/tournaments/{tournament_id}/scorers",
                headers=_headers(organiser), json={"scorer_id": scorer.id})
    match_id = fixtures[0]["id"]
    assert client.post(f"/matches/{match_id}/start", headers=_headers(scorer)).status_code == 200
    client.post(f"/matches/{match_id}/score", headers=_headers(scorer),
                json={"match_id": match_id, "team_a_score": score[0], "team_b_score": score[1]})
    return match_id


def test_organiser_is_told_about_each_new_application_with_a_link(db):
    organiser, _, _, tournament_id, captains, _ = _league(db)

    notes = _notifications(db, organiser, "registration_submitted")

    assert len(notes) == 2
    for _, team in captains:
        assert any(team["name"] in note.content for note in notes)
    assert all(note.link == f"#/registration-approvals/{tournament_id}" for note in notes)


def test_applicant_hears_the_decision_by_team_name(db):
    organiser, _, _, _, captains, registrations = _league(db)

    client.patch(f"/registrations/{registrations[0]['id']}/approve", headers=_headers(organiser))
    client.patch(f"/registrations/{registrations[1]['id']}/reject", headers=_headers(organiser))

    approved = _notifications(db, captains[0][0], "registration_status")
    rejected = _notifications(db, captains[1][0], "registration_status")
    assert captains[0][1]["name"] in approved[0].content and "approved" in approved[0].content
    assert "rejected" in rejected[0].content
    assert approved[0].link == "#/registrations"


def test_followers_and_teams_hear_fixtures_live_match_and_result(db):
    organiser, scorer, follower, tournament_id, captains, registrations = _league(db)

    match_id = _publish_and_play(db, organiser, scorer, tournament_id, registrations)

    assert _notifications(db, follower, "fixture_published")
    assert _notifications(db, follower, "match_live")
    assert _notifications(db, captains[0][0], "match_live")

    client.post(f"/matches/{match_id}/complete", headers=_headers(scorer))
    client.patch(f"/matches/{match_id}/score/verification", headers=_headers(organiser), json={"status": "verified"})
    assert client.post(f"/matches/{match_id}/result/finalize", headers=_headers(organiser)).status_code == 201

    for user in (follower, captains[0][0], captains[1][0]):
        result = _notifications(db, user, "result_published")
        assert len(result) == 1
        assert "2 - 1" in result[0].content
        assert result[0].link == f"#/details/{tournament_id}"

    # The only match is finished, so the tournament completes too.
    assert _notifications(db, follower, "tournament_completed")
    assert _notifications(db, captains[1][0], "tournament_completed")


def test_organiser_is_asked_to_finalize_when_the_scorer_ends_a_match(db):
    organiser, scorer, _, tournament_id, _, registrations = _league(db)
    match_id = _publish_and_play(db, organiser, scorer, tournament_id, registrations)

    assert client.post(f"/matches/{match_id}/complete", headers=_headers(scorer)).status_code == 200

    notes = _notifications(db, organiser, "match_completed")
    assert len(notes) == 1
    assert "verify and publish the result" in notes[0].content
    assert notes[0].link == f"#/verify/{tournament_id}"


def test_scorer_is_told_when_a_score_is_rejected(db):
    organiser, scorer, _, tournament_id, _, registrations = _league(db)
    match_id = _publish_and_play(db, organiser, scorer, tournament_id, registrations)
    client.post(f"/matches/{match_id}/complete", headers=_headers(scorer))

    client.patch(f"/matches/{match_id}/score/verification", headers=_headers(organiser), json={"status": "rejected"})

    notes = _notifications(db, scorer, "score_rejected")
    assert len(notes) == 1 and notes[0].link == "#/scoring"
    assigned = _notifications(db, scorer, "tournament_scorer_assignment")
    assert assigned and assigned[0].link == "#/scoring"


def test_disputes_notify_the_organiser_and_then_the_player(db):
    organiser, scorer, _, tournament_id, captains, registrations = _league(db)
    match_id = _publish_and_play(db, organiser, scorer, tournament_id, registrations)
    captain = captains[0][0]
    client.post("/player-team/team/{}/players/{}".format(
        captains[0][1]["id"],
        client.get("/player-team/profile/me", headers=_headers(captain)).json()["id"],
    ), headers=_headers(captain))

    created = client.post("/disputes/", headers=_headers(captain),
                          json={"match_id": match_id, "reason": "Incorrect score: the goal was offside."})
    assert created.status_code == 201, created.text

    raised = _notifications(db, organiser, "dispute_submitted")
    assert len(raised) == 1 and raised[0].link == "#/resolve"

    client.patch(f"/disputes/{created.json()['id']}/status", headers=_headers(organiser),
                 json={"status": "under_review"})
    updates = _notifications(db, captain, "dispute_update")
    assert updates and "under review" in updates[0].content


def test_follow_unfollow_and_status(db):
    organiser = _user(db, "organiser")
    fan = _user(db, "spectator")
    tournament = Tournament(
        name=f"Follow Cup {uuid4().hex[:6]}", format="round_robin", status="upcoming",
        start_date=datetime(2099, 1, 1, tzinfo=timezone.utc), end_date=datetime(2099, 1, 5, tzinfo=timezone.utc),
        registration_open_at=datetime(2098, 12, 1, tzinfo=timezone.utc),
        registration_close_at=datetime(2098, 12, 31, tzinfo=timezone.utc), organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    url = f"/tournaments/{tournament.id}/follow"

    assert client.get(url).status_code == 401
    assert client.get(url, headers=_headers(fan)).json() == {"following": False, "followers": 0}
    assert client.post(url, headers=_headers(fan)).json() == {"following": True, "followers": 1}
    assert client.post(url, headers=_headers(fan)).json() == {"following": True, "followers": 1}
    assert client.delete(url, headers=_headers(fan)).json() == {"following": False, "followers": 0}
    assert client.post("/tournaments/999999999/follow", headers=_headers(fan)).status_code == 404


def test_mark_all_read_only_touches_my_notifications(db):
    me = _user(db, "player")
    other = _user(db, "player")
    db.add_all([
        Notification(user_id=me.id, notification_type="x", content="one"),
        Notification(user_id=me.id, notification_type="x", content="two"),
        Notification(user_id=other.id, notification_type="x", content="theirs"),
    ])
    db.commit()

    response = client.patch("/notifications/read-all", headers=_headers(me))

    assert response.json() == {"updated": 2}
    assert client.get("/notifications/unread-count", headers=_headers(me)).json() == {"unread_count": 0}
    assert client.get("/notifications/unread-count", headers=_headers(other)).json() == {"unread_count": 1}


def test_notifications_are_pushed_live_only_after_commit(db):
    from app.realtime.redis_pubsub import pubsub_manager

    user = _user(db, "player")
    with patch.object(pubsub_manager, "event_loop", object()), \
            patch.object(pubsub_manager, "schedule_event") as schedule:
        db.add(Notification(user_id=user.id, notification_type="x", content="kept", link="#/details/1"))
        db.flush()
        schedule.assert_not_called()
        db.commit()

        assert schedule.call_count == 1
        event = schedule.call_args.args[0]
        assert event["type"] == "notification:new"
        assert event["payload"]["recipient_id"] == user.id
        assert event["payload"]["link"] == "#/details/1"
        assert isinstance(event["payload"]["notification_id"], int)

        schedule.reset_mock()
        db.add(Notification(user_id=user.id, notification_type="x", content="dropped"))
        db.flush()
        db.rollback()
        db.commit()
        schedule.assert_not_called()
