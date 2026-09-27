from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

EXPECTED_HEAD = "0001_phase2_schema"


def _script_directory() -> ScriptDirectory:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def test_alembic_has_single_expected_head() -> None:
    script = _script_directory()

    assert script.get_heads() == [EXPECTED_HEAD]


def test_initial_migration_has_no_parent_revision() -> None:
    script = _script_directory()
    revision = script.get_revision(EXPECTED_HEAD)

    assert revision is not None
    assert revision.down_revision is None
