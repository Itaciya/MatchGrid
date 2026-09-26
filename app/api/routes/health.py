import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.data_access.redis_client import test_redis_connection
from app.data_access.database import get_db


router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/database-session")
def database_session_test(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))

        logger.info("Database session health check successful")

        return {
            "message": "Database session is working"
        }

    except Exception:
        logger.exception("Database session health check failed")
        raise


@router.get("/redis")
def redis_health():
    result = test_redis_connection()

    if result == "Redis connection successful":
        logger.info("Redis health check successful")
    else:
        logger.error("Redis health check failed")

    return {
        "redis": result
    }
      