import pytest
from sqlalchemy.exc import DataError

from app.modules.match.models.match_result import MatchResult
from app.modules.match.models.match_result_correction import MatchResultCorrection
from app.modules.match.services.match_result_service import correct_match_result
from app.modules.score.models.score import Score
from test_match_result_finalization import (
    _auth_header,
    _finalize,
    _make_match,
    _make_score,
    client,
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


def _corrections(db, match):
    """Audit rows for this match only: the test database is shared and never cleaned."""
    return (
        db.query(MatchResultCorrection)
        .join(MatchResult, MatchResult.id == MatchResultCorrection.match_result_id)
        .filter(MatchResult.match_id == match.id)
    )


def _result(db, match):
    db.expire_all()
    return db.query(MatchResult).filter_by(match_id=match.id).one()


def test_reason_is_required(db):
    match, organiser = _finalized(db)

    response = client.patch(
        f"/matches/{match.id}/result",
        json={"team_a_score": 0, "team_b_score": 3},
        headers=_auth_header(organiser),
    )

    assert response.status_code == 422
    assert _corrections(db, match).count() == 0
    result = _result(db, match)
    assert (result.team_a_score, result.team_b_score) == (2, 1)


@pytest.mark.parametrize("reason", ["", "   "])
def test_blank_reason_is_rejected(db, reason):
    match, organiser = _finalized(db)

    assert _correct(match, organiser, 0, 3, reason=reason).status_code == 422
    assert _corrections(db, match).count() == 0


def test_client_cannot_set_the_outcome_directly(db):
    match, organiser = _finalized(db)

    response = client.patch(
        f"/matches/{match.id}/result",
        json={
            "team_a_score": 0,
            "team_b_score": 3,
            "reason": "typo",
            "outcome": "draw",
        },
        headers=_auth_header(organiser),
    )

    assert response.status_code == 422
    assert _corrections(db, match).count() == 0
    assert _result(db, match).outcome == "team_a_win"


def test_reason_is_stored_trimmed_in_the_audit_row(db):
    match, organiser = _finalized(db)

    _correct(match, organiser, 1, 1, reason="  Typo in the second half  ")

    row = _corrections(db, match).one()
    assert row.reason == "Typo in the second half"
    assert row.corrected_at is not None


def test_successive_corrections_form_an_audit_chain(db):
    match, organiser = _finalized(db, 2, 1)

    assert _correct(match, organiser, 1, 1).status_code == 200
    assert _correct(match, organiser, 0, 2).status_code == 200

    rows = _corrections(db, match).order_by(MatchResultCorrection.id).all()
    assert len(rows) == 2
    first, second = rows
    assert (first.old_team_a_score, first.old_team_b_score) == (2, 1)
    assert (first.new_team_a_score, first.new_team_b_score) == (1, 1)
    assert (first.old_outcome, first.new_outcome) == ("team_a_win", "draw")
    assert (second.old_team_a_score, second.old_team_b_score) == (1, 1)
    assert (second.new_team_a_score, second.new_team_b_score) == (0, 2)
    assert (second.old_outcome, second.new_outcome) == ("draw", "team_b_win")
    assert {first.corrected_by_id, second.corrected_by_id} == {organiser.id}


def test_correction_keeps_the_score_in_step_with_the_result(db):
    match, organiser = _finalized(db, 2, 1)

    assert _correct(match, organiser, 0, 3).status_code == 200

    db.expire_all()
    score = db.query(Score).filter_by(match_id=match.id).one()
    assert (score.team_a_score, score.team_b_score) == (0, 3)
    assert score.verification_status == "verified"
    assert score.is_verified is True
    assert score.reviewed_by_id == organiser.id


def test_correction_does_not_reopen_the_match(db):
    match, organiser = _finalized(db)

    assert _correct(match, organiser, 0, 3).status_code == 200

    db.refresh(match)
    assert match.status == "completed"


def test_correcting_a_win_to_a_draw_clears_winner_and_loser(db):
    match, organiser = _finalized(db, 2, 1)

    response = _correct(match, organiser, 2, 2)

    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "draw"
    assert data["winner_team_id"] is None
    assert data["loser_team_id"] is None


def test_database_failure_rolls_back_result_score_and_audit(db):
    match, organiser = _finalized(db, 2, 1)

    # 501 characters passes the service but not the VARCHAR(500) column, so the
    # failure happens inside the database after the result and score changed.
    with pytest.raises(DataError):
        correct_match_result(db, match.id, organiser.id, 0, 9, "x" * 501)

    db.expire_all()
    result = db.query(MatchResult).filter_by(match_id=match.id).one()
    score = db.query(Score).filter_by(match_id=match.id).one()
    assert (result.team_a_score, result.team_b_score) == (2, 1)
    assert result.outcome == "team_a_win"
    assert (score.team_a_score, score.team_b_score) == (2, 1)
    assert _corrections(db, match).count() == 0
