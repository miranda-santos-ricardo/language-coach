import importlib.util
from pathlib import Path
from types import ModuleType


def _reference_data_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0002_phase2_reference_data.py"
    )

    spec = importlib.util.spec_from_file_location(
        "phase2_reference_data_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_languages_are_complete() -> None:
    migration = _reference_data_migration()

    assert {
        row["code"]: row["name"]
        for row in migration.LANGUAGE_ROWS
    } == {
        "fr": "French",
        "en": "English",
    }


def test_reference_variants_include_required_and_extensible_set() -> None:
    migration = _reference_data_migration()

    variants = {
        row["code"]: row
        for row in migration.VARIANT_ROWS
    }

    assert set(variants) == {
        "fr-CA",
        "fr-FR",
        "en-CA",
        "en-US",
        "en-GB",
    }
    assert variants["fr-CA"]["language_code"] == "fr"
    assert variants["fr-CA"]["regional_focus"] == "Québec"
    assert variants["fr-FR"]["language_code"] == "fr"
    assert variants["en-CA"]["language_code"] == "en"


def test_communication_registers_support_production_and_comprehension() -> None:
    migration = _reference_data_migration()

    registers = {
        row["code"]: row
        for row in migration.REGISTER_ROWS
    }

    assert set(registers) == {
        "professional",
        "formal_executive",
        "everyday",
        "conversational",
        "colloquial",
    }

    for register in registers.values():
        assert register["production_allowed"] is True
        assert register["comprehension_allowed"] is True


def test_colloquial_is_explicitly_available_for_production() -> None:
    migration = _reference_data_migration()

    colloquial = next(
        row
        for row in migration.REGISTER_ROWS
        if row["code"] == "colloquial"
    )

    assert colloquial["production_allowed"] is True
    assert colloquial["comprehension_allowed"] is True
