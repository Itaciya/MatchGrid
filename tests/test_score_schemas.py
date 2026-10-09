from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.score.schemas.score import ScoreCreate, ScoreResponse, ScoreUpdate


# --- ScoreCreate ---

def test_valid_score_create_passes():
    score = ScoreCreate(match_id=1, team_a_score=3, team_b_score=2)
    assert score.match_id == 1
    assert score.team_a_score == 3
    assert score.team_b_score == 2


def test_zero_scores_are_valid():
    score = ScoreCreate(match_id=1, team_a_score=0, team_b_score=0)
    assert score.team_a_score == 0
    assert score.team_b_score == 0


@pytest.mark.parametrize("field", ["team_a_score", "team_b_score"])
def test_negative_score_is_rejected_with_clear_message(field):
    data = {"match_id": 1, "team_a_score": 1, "team_b_score": 1}
    data[field] = -1

    with pytest.raises(ValidationError) as exc_info:
        ScoreCreate(**data)

    assert "greater than or equal to 0" in str(exc_info.value)


@pytest.mark.parametrize("missing", ["match_id", "team_a_score", "team_b_score"])
def test_missing_required_field_is_rejected(missing):
    data = {"match_id": 1, "team_a_score": 1, "team_b_score": 1}
    del data[missing]

    with pytest.raises(ValidationError):
        ScoreCreate(**data)


@pytest.mark.parametrize("bad_value", ["3", 2.5, True, None])
def test_non_integer_score_is_rejected(bad_value):
    with pytest.raises(ValidationError):
        ScoreCreate(match_id=1, team_a_score=bad_value, team_b_score=1)


@pytest.mark.parametrize("bad_match_id", [0, -5, "1"])
def test_invalid_match_id_is_rejected(bad_match_id):
    with pytest.raises(ValidationError):
        ScoreCreate(match_id=bad_match_id, team_a_score=1, team_b_score=1)


def test_client_cannot_submit_is_verified():
    with pytest.raises(ValidationError):
        ScoreCreate(match_id=1, team_a_score=1, team_b_score=1, is_verified=True)


# --- ScoreUpdate ---

def test_partial_update_with_one_score_passes():
    update = ScoreUpdate(team_a_score=5)
    assert update.team_a_score == 5
    assert update.team_b_score is None


def test_update_with_both_scores_passes():
    update = ScoreUpdate(team_a_score=5, team_b_score=4)
    assert update.team_b_score == 4


def test_empty_update_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ScoreUpdate()

    assert "at least one" in str(exc_info.value)


def test_update_with_only_nulls_is_rejected():
    with pytest.raises(ValidationError):
        ScoreUpdate(team_a_score=None, team_b_score=None)


def test_update_with_negative_score_is_rejected():
    with pytest.raises(ValidationError):
        ScoreUpdate(team_a_score=-1)


def test_update_cannot_set_is_verified():
    with pytest.raises(ValidationError):
        ScoreUpdate(team_a_score=1, is_verified=True)


# --- ScoreResponse ---

def test_response_serializes_from_orm_like_object():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)

    class FakeScore:
        id = 1
        match_id = 7
        team_a_score = 3
        team_b_score = 1
        is_verified = False
        verification_status = "pending"
        reviewed_by_id = None
        reviewed_at = None
        created_at = now
        updated_at = now

    response = ScoreResponse.model_validate(FakeScore())
    assert response.match_id == 7
    assert response.team_a_score == 3
    assert response.is_verified is False
