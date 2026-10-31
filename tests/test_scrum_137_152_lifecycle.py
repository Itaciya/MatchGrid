from app.modules.match.services.standings_service import get_tournament_standings
from app.modules.official_assignment.models.official_assignment import OfficialAssignment
from app.modules.official_assignment.models.tournament_scorer_assignment import TournamentScorerAssignment
from test_match_result_finalization import (
    _auth_header,
    _make_match,
    _make_user,
    client,
)


def _call(method, path, user, body=None):
    return client.request(method, path, json=body, headers=_auth_header(user))


def _points(db, match):
    db.expire_all()
    table = get_tournament_standings(db, match.tournament_id)
    return {row["team_id"]: row["points"] for row in table}


def test_match_goes_from_scheduled_to_corrected_result(db):
    match, organiser = _make_match(db)
    match.status = "scheduled"
    official = _make_user(db, "scorer")
    stranger = _make_user(db, "scorer")
    db.add(
        TournamentScorerAssignment(
            tournament_id=match.tournament_id,
            scorer_id=official.id,
            status="active",
        )
    )
    db.commit()
    base = f"/matches/{match.id}"
    score = {"match_id": match.id, "team_a_score": 2, "team_b_score": 1}

    # Start: only the assigned official
    assert _call("POST", f"{base}/start", stranger).status_code == 403
    started = _call("POST", f"{base}/start", official)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "live"
    assert started.json()["started_at"] is not None

    # Score: only the assigned official; it starts pending
    assert _call("POST", f"{base}/score", stranger, score).status_code == 403
    submitted = _call("POST", f"{base}/score", official, score)
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["verification_status"] == "pending"

    # An unverified score cannot be published, and standings are untouched
    assert _call("POST", f"{base}/result/finalize", organiser).status_code == 409
    assert _points(db, match) == {match.team_a_id: 0, match.team_b_id: 0}

    # Verification: owning organiser only; a verified score is locked
    assert _call("PATCH", f"{base}/score/verification", official, {"status": "verified"}).status_code == 403
    verified = _call("PATCH", f"{base}/score/verification", organiser, {"status": "verified"})
    assert verified.status_code == 200, verified.text
    assert _call("PATCH", f"{base}/score", official, {"team_a_score": 9}).status_code == 409

    # Finalization: exactly once, and standings follow
    finalized = _call("POST", f"{base}/result/finalize", organiser)
    assert finalized.status_code == 201, finalized.text
    assert finalized.json()["outcome"] == "team_a_win"
    assert _call("POST", f"{base}/result/finalize", organiser).status_code == 409
    db.refresh(match)
    assert match.status == "completed"
    assert _points(db, match) == {match.team_a_id: 3, match.team_b_id: 0}

    # Correction: owning organiser only, and standings follow
    correction = {"team_a_score": 0, "team_b_score": 3, "reason": "Scorer typo"}
    assert _call("PATCH", f"{base}/result", official, correction).status_code == 403
    corrected = _call("PATCH", f"{base}/result", organiser, correction)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["outcome"] == "team_b_win"
    assert _points(db, match) == {match.team_a_id: 0, match.team_b_id: 3}

    # The completed match's score stays locked
    assert _call("PATCH", f"{base}/score", official, {"team_a_score": 5}).status_code == 409
