"""Create Phase 2 domain schema.

Revision ID: 0001_phase2_schema
Revises:
Create Date: 2026-09-26

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_phase2_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(display_name)) > 0",
            name=op.f("ck_users_display_name_not_blank"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )

    op.create_table(
        "languages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_languages")),
        sa.UniqueConstraint("code", name=op.f("uq_languages_code")),
    )

    op.create_table(
        "communication_registers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "production_allowed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "comprehension_allowed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "production_allowed OR comprehension_allowed",
            name=op.f("ck_communication_registers_usable_for_at_least_one_mode"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_communication_registers"),
        ),
        sa.UniqueConstraint(
            "code",
            name=op.f("uq_communication_registers_code"),
        ),
    )

    op.create_table(
        "language_variants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("language_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=35), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("regional_focus", sa.String(length=100), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["language_id"],
            ["languages.id"],
            name=op.f("fk_language_variants_language_id_languages"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_language_variants")),
        sa.UniqueConstraint(
            "code",
            name=op.f("uq_language_variants_code"),
        ),
    )

    op.create_table(
        "language_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("language_variant_id", sa.Integer(), nullable=False),
        sa.Column("cefr_level", sa.String(length=2), nullable=False),
        sa.Column(
            "default_production_register_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cefr_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')",
            name=op.f("ck_language_profiles_cefr_level"),
        ),
        sa.ForeignKeyConstraint(
            ["default_production_register_id"],
            ["communication_registers.id"],
            name=op.f(
                "fk_language_profiles_default_production_register_id_communication_registers"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["language_variant_id"],
            ["language_variants.id"],
            name=op.f(
                "fk_language_profiles_language_variant_id_language_variants"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_language_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_language_profiles")),
        sa.UniqueConstraint(
            "user_id",
            "language_variant_id",
            name="uq_language_profiles_user_language_variant",
        ),
    )

    op.create_table(
        "language_profile_comprehension_registers",
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("communication_register_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["communication_register_id"],
            ["communication_registers.id"],
            name=op.f(
                "fk_language_profile_comprehension_registers_communication_register_id_communication_registers"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["language_profile_id"],
            ["language_profiles.id"],
            name=op.f(
                "fk_language_profile_comprehension_registers_language_profile_id_language_profiles"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "language_profile_id",
            "communication_register_id",
            name=op.f("pk_language_profile_comprehension_registers"),
        ),
    )


def downgrade() -> None:
    op.drop_table("language_profile_comprehension_registers")
    op.drop_table("language_profiles")
    op.drop_table("language_variants")
    op.drop_table("communication_registers")
    op.drop_table("languages")
    op.drop_table("users")
