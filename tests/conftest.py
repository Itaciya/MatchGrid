import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data_access.database import SessionLocal


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()