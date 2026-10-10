import pytest

from app.modules.match.models.match_result import MatchResult
from app.modules.match.models.match_result_correction import MatchResultCorrection
from app.modules.match.services.match_result_service import correct_match_result
from app.modules.match.services.standings_service import get_tournament_standings
from test_match_result_finalization import (
    _auth_header,
    _finalize,
    _make_match,
    _make_score,
    _make_user,
    client,
)


def _corrections_for(db, match):
    """Audit rows for this match only (the test database is shared and never cleaned)."""
    return (
        db.query(MatchResultCorrection)
        .join(MatchResult, MatchResult.id == MatchResultCorrection.match_result_id)
        .filter(MatchResult.match_id == match.id)
    )


def _finalized(db, a=2, b=1):
    match, organiser = _make_match(db)
    _make_score(db, match, team_a_score=a, team_b_score=b)
    assert _finalize(match, organiser).status_code == 201
    return match, organiser


def _correct(match, user, a, b, reason="Scorer typo"):
    return client.patch(
        f"/matches/{match.id}/result",
        json={"team_a_score": a, "team_b_score": b, "reason": reason},
        headers=_auth_header(user),
    )


def test_authorized_correction_updates_result_and_score(db):
    match, organiser = _finalized(db, 2, 1)

    response = _correct(match, organiser, 0, 3)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["outcome"] == "team_b_win"
    assert data["winner_team_id"] == match.team_b_id
    assert (data["team_a_score"], data["team_b_score"]) == (0, 3)


def test_correction_writes_an_audit_row(db):
    match, organiser = _finalized(db, 2, 1)

    _correct(match, organiser, 1, 1)

    row = _corrections_for(db, match).one()
    assert (row.old_team_a_score, row.new_team_a_score) == (2, 1)
    assert (row.old_outcome, row.new_outcome) == ("team_a_win", "draw")
    assert row.corrected_by_id == organiser.id


def test_other_organiser_cannot_correct(db):
    match, _ = _finalized(db)
    other = _make_user(db, "organiser")

    assert _correct(match, other, 0, 5).status_code == 403
    assert _corrections_for(db, match).count() == 0


@pytest.mark.parametrize("role", ["scorer", "official", "player", "spectator"])
def test_other_roles_cannot_correct(db, role):
    match, _ = _finalized(db)

    assert _correct(match, _make_user(db, role), 0, 5).status_code == 403


def test_unauthenticated_cannot_correct(db):
    match, _ = _finalized(db)

    response = client.patch(
        f"/matches/{match.id}/result",
        json={"team_a_score": 0, "team_b_score": 5, "reason": "x"},
    )

    assert response.status_code in (401, 403)


def test_cannot_correct_a_match_with_no_finalized_result(db):
    match, organiser = _make_match(db)
    _make_score(db, match)

    assert _correct(match, organiser, 1, 0).status_code == 404


def test_unchanged_scores_are_rejected(db):
    match, organiser = _finalized(db, 2, 1)

    assert _correct(match, organiser, 2, 1).status_code == 400


def test_negative_scores_are_rejected(db):
    match, organiser = _finalized(db)

    assert _correct(match, organiser, -1, 0).status_code == 422


def test_standings_reflect_the_corrected_result(db):
    match, organiser = _finalized(db, 2, 1)
    before = {
        r["team_id"]: r for r in get_tournament_standings(db, match.tournament_id)
    }
    assert before[match.team_a_id]["points"] == 3

    _correct(match, organiser, 0, 4)

    db.expire_all()
    after = {
        r["team_id"]: r for r in get_tournament_standings(db, match.tournament_id)
    }
    assert after[match.team_a_id]["points"] == 0
    assert after[match.team_b_id]["points"] == 3


def test_failed_correction_rolls_back_everything(db, monkeypatch):
    match, organiser = _finalized(db, 2, 1)

    def boom():
        raise RuntimeError("forced failure")

    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError):
        correct_match_result(db, match.id, organiser.id, 0, 9, "x")
    monkeypatch.undo()

    db.expire_all()
    result = db.query(MatchResult).filter_by(match_id=match.id).one()
    assert (result.team_a_score, result.team_b_score) == (2, 1)
    assert _corrections_for(db, match).count() == 0
