from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.db.base import Base
from app.models import CEFRLevel, CommunicationRegister, LanguageProfile


def test_phase_2_tables_are_registered_in_metadata() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "languages",
        "language_variants",
        "communication_registers",
        "language_profiles",
        "language_profile_comprehension_registers",
    }


def test_all_model_relationships_configure_successfully() -> None:
    configure_mappers()


def test_cefr_level_is_closed_and_stable() -> None:
    assert [level.value for level in CEFRLevel] == [
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ]


def test_language_profile_is_unique_per_user_and_variant() -> None:
    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in LanguageProfile.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert unique_constraints["uq_language_profiles_user_language_variant"] == (
        "user_id",
        "language_variant_id",
    )


def test_language_profile_cefr_has_database_check_constraint() -> None:
    check_constraints = {
        constraint.name
        for constraint in LanguageProfile.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_language_profiles_cefr_level" in check_constraints


def test_comprehension_association_uses_composite_primary_key() -> None:
    association = Base.metadata.tables[
        "language_profile_comprehension_registers"
    ]

    assert [column.name for column in association.primary_key.columns] == [
        "language_profile_id",
        "communication_register_id",
    ]


def test_colloquial_register_can_support_production_and_comprehension() -> None:
    register = CommunicationRegister(
        code="colloquial",
        display_name="Colloquial",
        production_allowed=True,
        comprehension_allowed=True,
    )

    assert register.production_allowed is True
    assert register.comprehension_allowed is True
