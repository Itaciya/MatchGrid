
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.data_access.database import get_db
from app.modules.audit.models.audit_log import AuditLog
from app.modules.audit.schemas import AuditLogResponse
from app.modules.user.models import User

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def require_audit_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow only explicitly configured user IDs to review audit logs."""
    raw_ids = settings.AUDIT_ADMIN_USER_IDS
    allowed_ids = {
        int(value.strip())
        for value in raw_ids.split(",")
        if value.strip().isdigit()
    }

    if current_user.id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )

    return current_user


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_audit_admin),
):
    """Return newest audit logs first."""
    return (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
