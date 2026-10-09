
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.dispute.schemas.dispute import (
    DisputeCreate,
    DisputeResponse,
    DisputeUpdate,
)


# --- DisputeCreate ---


def test_valid_dispute_create_passes():
    dispute = DisputeCreate(
        match_id=1,
        reason="Incorrect match result",
    )

    assert dispute.match_id == 1
    assert dispute.reason == "Incorrect match result"


@pytest.mark.parametrize("missing", ["match_id", "reason"])
def test_missing_required_field_is_rejected(missing):
    data = {
        "match_id": 1,
        "reason": "Incorrect match result",
    }
    del data[missing]

    with pytest.raises(ValidationError):
        DisputeCreate(**data)


@pytest.mark.parametrize("bad_match_id", [0, -1, "1", True])
def test_invalid_match_id_is_rejected(bad_match_id):
    with pytest.raises(ValidationError):
        DisputeCreate(
            match_id=bad_match_id,
            reason="Incorrect match result",
        )


@pytest.mark.parametrize("bad_reason", ["", None])
def test_invalid_reason_is_rejected(bad_reason):
    with pytest.raises(ValidationError):
        DisputeCreate(match_id=1, reason=bad_reason)


def test_client_cannot_submit_unknown_fields():
    with pytest.raises(ValidationError):
        DisputeCreate(
            match_id=1,
            reason="Incorrect match result",
            user_id=99,
        )


# --- DisputeUpdate ---


def test_partial_update_with_reason_passes():
    update = DisputeUpdate(reason="Updated dispute reason")

    assert update.reason == "Updated dispute reason"


def test_update_with_resolution_passes():
    update = DisputeUpdate(resolution="Score corrected")

    assert update.resolution == "Score corrected"


def test_update_with_status_passes():
    update = DisputeUpdate(status="resolved")

    assert update.status == "resolved"


def test_empty_update_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        DisputeUpdate()

    assert "At least one field" in str(exc_info.value)


def test_update_with_empty_reason_is_rejected():
    with pytest.raises(ValidationError):
        DisputeUpdate(reason="")


def test_update_cannot_set_unknown_fields():
    with pytest.raises(ValidationError):
        DisputeUpdate(user_id=99)


# --- DisputeResponse ---


def test_response_validates_dispute_data():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)

    class FakeDispute:
        id = 1
        match_id = 7
        user_id = 2
        reason = "Incorrect match result"
        status = "pending"
        resolution = None
        created_at = now
        updated_at = now

    response = DisputeResponse.model_validate(FakeDispute())

    assert response.id == 1
    assert response.match_id == 7
    assert response.user_id == 2
    assert response.status == "pending"
    assert response.resolution is None


def test_response_accepts_resolution():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)

    class FakeDispute:
        id = 1
        match_id = 7
        user_id = 2
        reason = "Incorrect match result"
        status = "resolved"
        resolution = "Score corrected"
        created_at = now
        updated_at = now

    response = DisputeResponse.model_validate(FakeDispute())

    assert response.status == "resolved"
    assert response.resolution == "Score corrected"
