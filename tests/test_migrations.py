import subprocess
import sys
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_DIR = PROJECT_ROOT / "alembic"


def test_database_is_at_latest_migration(db):
    """The applied migration in the DB must match the head revision on disk."""
    script = ScriptDirectory(str(ALEMBIC_DIR))
    head_revision = script.get_current_head()

    result = db.execute(text("SELECT version_num FROM alembic_version"))
    current_revision = result.scalar()

    assert current_revision == head_revision, (
        f"Database is at revision '{current_revision}', but the latest "
        f"migration on disk is '{head_revision}'. Run `alembic upgrade head`."
    )


def test_no_pending_model_changes():
    """Mirrors `alembic check`: fails if models have drifted from migrations."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "`alembic check` detected model/migration drift:\n"
        f"{result.stdout}\n{result.stderr}"
    )
