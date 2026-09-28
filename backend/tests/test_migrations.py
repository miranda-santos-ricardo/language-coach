from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

SCHEMA_REVISION = "0001_phase2_schema"
REFERENCE_DATA_REVISION = "ba35d4c616d6"
EXPECTED_HEAD = REFERENCE_DATA_REVISION


def _script_directory() -> ScriptDirectory:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def test_alembic_has_single_expected_head() -> None:
    script = _script_directory()

    assert script.get_heads() == [EXPECTED_HEAD]


def test_initial_migration_has_no_parent_revision() -> None:
    script = _script_directory()
    revision = script.get_revision(SCHEMA_REVISION)

    assert revision is not None
    assert revision.down_revision is None


def test_reference_data_migration_follows_schema_migration() -> None:
    script = _script_directory()

    assert script.get_heads() == [EXPECTED_HEAD]
