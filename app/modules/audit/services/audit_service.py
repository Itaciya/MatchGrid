import logging

from sqlalchemy.orm import Session

from app.modules.audit.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def record_audit_event(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
) -> AuditLog:
    """Record a safe, structured audit event."""
    if not action.strip() or not resource_type.strip():
        raise ValueError("Action and resource type are required")

    event = AuditLog(
        user_id=user_id,
        action=action.strip(),
        resource_type=resource_type.strip(),
        resource_id=(
            str(resource_id) if resource_id is not None else None
        ),
    )

    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        logger.exception("Failed to persist audit event")
        raise

    return event