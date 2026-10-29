import sys
from pathlib import Path

import fakeredis
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv()


def _use_test_database() -> None:
    """Run the suite only against a database whose name ends in "_test".

    The app reads DATABASE_URL when app.data_access.database is imported, so
    the override has to happen before that import. Without a test database the
    run is aborted, so tests can never write to the development database.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        candidate = os.environ.get("DATABASE_URL", "")
        if candidate and (make_url(candidate).database or "").endswith("_test"):
            url = candidate
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is not set. Create a database whose name ends "
            "in '_test', run 'alembic upgrade head' against it, and set "
            "TEST_DATABASE_URL.",
            returncode=2,
        )
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.exit(
            f"Refusing to run tests against '{database}': the database name "
            "must end in '_test'.",
            returncode=2,
        )
    os.environ["DATABASE_URL"] = url


_use_test_database()

from app.data_access.database import SessionLocal

# Import all SQLAlchemy models before tests start.
from app.modules.user.models import User
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.match.models.match_result_correction import MatchResultCorrection
from app.modules.match.models.tournament_round import TournamentRound
from app.modules.score.models.score import Score
from app.modules.official_assignment.models.official_assignment import OfficialAssignment


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """In-memory Redis stand-in so tests don't need a live Redis server.

    autouse=True because get_current_user (app/core/dependencies.py) now
    also calls get_redis as of SCRUM-51, and it's exercised indirectly by
    many existing protected-route tests that don't request this fixture
    by name.
    """
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "app.modules.user.services.auth_service.get_redis",
        lambda: fake,
    )
    monkeypatch.setattr(
        "app.core.dependencies.get_redis",
        lambda: fake,
    )
    return fake


@pytest.fixture
def anyio_backend():
    return "asyncio"

