from sqlalchemy import text


EXPECTED_INDEXES = {
    "matches": {"ix_matches_status", "ix_matches_scheduled_at"},
    "tournaments": {"ix_tournaments_status"},
    "registrations": {"ix_registrations_status"},
    "notifications": {"ix_notifications_user_id_is_read"},
}


def _existing_index_names(db, table_name):
    result = db.execute(
        text(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return {row[0] for row in result}


def test_required_indexes_exist(db):
    for table_name, expected_names in EXPECTED_INDEXES.items():
        existing_names = _existing_index_names(db, table_name)
        missing = expected_names - existing_names
        assert not missing, f"Missing indexes on '{table_name}': {missing}"


def test_notification_user_id_has_no_redundant_standalone_index(db):
    existing_names = _existing_index_names(db, "notifications")
    assert "ix_notifications_user_id" not in existing_names
    assert "ix_notifications_user_id_is_read" in existing_names
