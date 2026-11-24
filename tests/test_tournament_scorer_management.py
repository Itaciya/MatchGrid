from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User

client = TestClient(app)


def _user(db, role):
    user = User(
        email=f"scorer_mgmt_{uuid4()}@example.com",
        password_hash="not-used",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _tournament(db, organiser):
    tournament = Tournament(
        name=f"Scorer Cup {uuid4().hex[:8]}",
        format="round_robin",
        start_date=datetime(2099, 5, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 5, 5, tzinfo=timezone.utc),
        registration_open_at=datetime(2099, 3, 1, tzinfo=timezone.utc),
        registration_close_at=datetime(2099, 4, 1, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=organiser.id,
    )
    db.add(tournament)
    db.commit()
    return tournament


def test_organiser_assigns_lists_and_removes_a_scorer(db):
    organiser = _user(db, "organiser")
    scorer = _user(db, "scorer")
    tournament = _tournament(db, organiser)
    base = f"/official-assignments/tournaments/{tournament.id}/scorers"

    assign = client.post(base, json={"scorer_id": scorer.id}, headers=_headers(organiser))
    assert assign.status_code == 201

    listing = client.get(base, headers=_headers(organiser))
    assert [item["id"] for item in listing.json()] == [scorer.id]

    remove = client.delete(f"{base}/{scorer.id}", headers=_headers(organiser))
    assert remove.status_code == 204
    assert client.get(base, headers=_headers(organiser)).json() == []

    # A removed scorer can be assigned again.
    again = client.post(base, json={"scorer_id": scorer.id}, headers=_headers(organiser))
    assert again.status_code == 201


def test_other_organiser_cannot_manage_scorers(db):
    organiser = _user(db, "organiser")
    other = _user(db, "organiser")
    scorer = _user(db, "scorer")
    tournament = _tournament(db, organiser)
    base = f"/official-assignments/tournaments/{tournament.id}/scorers"
    client.post(base, json={"scorer_id": scorer.id}, headers=_headers(organiser))

    assert client.get(base, headers=_headers(other)).status_code == 403
    assert client.delete(f"{base}/{scorer.id}", headers=_headers(other)).status_code == 403


def test_removing_an_unassigned_scorer_returns_404(db):
    organiser = _user(db, "organiser")
    scorer = _user(db, "scorer")
    tournament = _tournament(db, organiser)

    response = client.delete(
        f"/official-assignments/tournaments/{tournament.id}/scorers/{scorer.id}",
        headers=_headers(organiser),
    )

    assert response.status_code == 404
