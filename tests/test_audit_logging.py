
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.modules.audit.models.audit_log import AuditLog
from app.modules.audit.services.audit_service import record_audit_event


def test_record_audit_event_creates_and_commits_log():
    db = MagicMock()
    db.refresh.side_effect = lambda event: setattr(
        event, "timestamp", datetime.now(timezone.utc)
    )

    event = record_audit_event(
        db,
        user_id=7,
        action="auth.login_success",
        resource_type="user",
        resource_id=7,
    )

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(event)

    assert isinstance(event, AuditLog)
    assert event.user_id == 7
    assert event.action == "auth.login_success"
    assert event.resource_type == "user"
    assert event.resource_id == "7"


def test_record_audit_event_rejects_empty_action():
    db = MagicMock()

    with pytest.raises(ValueError):
        record_audit_event(
            db,
            user_id=7,
            action=" ",
            resource_type="user",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_record_audit_event_rolls_back_on_database_error():
    db = MagicMock()
    db.commit.side_effect = RuntimeError("database error")

    with pytest.raises(RuntimeError):
        record_audit_event(
            db,
            user_id=7,
            action="auth.login_success",
            resource_type="user",
        )

    db.rollback.assert_called_once()
