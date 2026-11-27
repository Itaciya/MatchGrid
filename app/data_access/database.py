import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app.data_access.base import Base
from sqlalchemy.engine import make_url

# Always the project's own .env (next to alembic.ini). A bare load_dotenv()
# searches upward from this file and would pick up a stray app/.env first,
# so the API and the migrations could end up on different databases.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

if os.getenv("MATCHGRID_E2E") == "1":
    database_name = make_url(DATABASE_URL).database or ""

    if not database_name.endswith("_test"):
        raise RuntimeError(
            f"E2E mode requires a test database. Refusing to connect to '{database_name}'."
        )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def test_database_connection():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return "Database connection successful"

    except SQLAlchemyError as e:
        return f"Database connection failed: {e}"