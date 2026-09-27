"""Insert Phase 2 reference data.

Revision ID: 0002_phase2_reference_data
Revises: 0001_phase2_schema
Create Date: 2026-09-26

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_phase2_reference_data"
down_revision: str | Sequence[str] | None = "0001_phase2_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LANGUAGE_ROWS = (
    {"code": "fr", "name": "French", "is_active": True},
    {"code": "en", "name": "English", "is_active": True},
)

VARIANT_ROWS = (
    {
        "language_code": "fr",
        "code": "fr-CA",
        "display_name": "French — Canada / Québec",
        "country_code": "CA",
        "regional_focus": "Québec",
        "is_active": True,
    },
    {
        "language_code": "fr",
        "code": "fr-FR",
        "display_name": "French — France",
        "country_code": "FR",
        "regional_focus": None,
        "is_active": True,
    },
    {
        "language_code": "en",
        "code": "en-CA",
        "display_name": "English — Canada",
        "country_code": "CA",
        "regional_focus": None,
        "is_active": True,
    },
    {
        "language_code": "en",
        "code": "en-US",
        "display_name": "English — United States",
        "country_code": "US",
        "regional_focus": None,
        "is_active": True,
    },
    {
        "language_code": "en",
        "code": "en-GB",
        "display_name": "English — United Kingdom",
        "country_code": "GB",
        "regional_focus": None,
        "is_active": True,
    },
)

REGISTER_ROWS = (
    {
        "code": "professional",
        "display_name": "Professional",
        "production_allowed": True,
        "comprehension_allowed": True,
        "is_active": True,
    },
    {
        "code": "formal_executive",
        "display_name": "Formal / Executive",
        "production_allowed": True,
        "comprehension_allowed": True,
        "is_active": True,
    },
    {
        "code": "everyday",
        "display_name": "Everyday",
        "production_allowed": True,
        "comprehension_allowed": True,
        "is_active": True,
    },
    {
        "code": "conversational",
        "display_name": "Conversational",
        "production_allowed": True,
        "comprehension_allowed": True,
        "is_active": True,
    },
    {
        "code": "colloquial",
        "display_name": "Colloquial",
        "production_allowed": True,
        "comprehension_allowed": True,
        "is_active": True,
    },
)


def upgrade() -> None:
    languages = sa.table(
        "languages",
        sa.column("id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )

    variants = sa.table(
        "language_variants",
        sa.column("language_id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("country_code", sa.String()),
        sa.column("regional_focus", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )

    registers = sa.table(
        "communication_registers",
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("production_allowed", sa.Boolean()),
        sa.column("comprehension_allowed", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )

    op.bulk_insert(languages, list(LANGUAGE_ROWS))
    op.bulk_insert(registers, list(REGISTER_ROWS))

    for row in VARIANT_ROWS:
        language_id = (
            sa.select(languages.c.id)
            .where(languages.c.code == row["language_code"])
            .scalar_subquery()
        )

        op.execute(
            sa.insert(variants).values(
                language_id=language_id,
                code=row["code"],
                display_name=row["display_name"],
                country_code=row["country_code"],
                regional_focus=row["regional_focus"],
                is_active=row["is_active"],
            )
        )


def downgrade() -> None:
    languages = sa.table(
        "languages",
        sa.column("code", sa.String()),
    )

    variants = sa.table(
        "language_variants",
        sa.column("code", sa.String()),
    )

    registers = sa.table(
        "communication_registers",
        sa.column("code", sa.String()),
    )

    op.execute(
        variants.delete().where(
            variants.c.code.in_([row["code"] for row in VARIANT_ROWS])
        )
    )
    op.execute(
        registers.delete().where(
            registers.c.code.in_([row["code"] for row in REGISTER_ROWS])
        )
    )
    op.execute(
        languages.delete().where(
            languages.c.code.in_([row["code"] for row in LANGUAGE_ROWS])
        )
    )
