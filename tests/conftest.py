import sys
from pathlib import Path

import fakeredis
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
