from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.data_access.redis_client import test_redis_connection
from app.data_access.database import get_db


router = APIRouter()


@router.get("/database-session")
def database_session_test(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))

    return {
        "message": "Database session is working"
    }

@router.get("/redis")
def redis_health():
    return {
        "redis": test_redis_connection()
    }