import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import language_profile_comprehension_registers
from app.models.enums import CEFRLevel
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.communication_register import CommunicationRegister
    from app.models.language_variant import LanguageVariant
    from app.models.user import User


class LanguageProfile(TimestampMixin, Base):
    __tablename__ = "language_profiles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "language_variant_id",
            name="uq_language_profiles_user_language_variant",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    language_variant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("language_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cefr_level: Mapped[CEFRLevel] = mapped_column(
        Enum(
            CEFRLevel,
            name="cefr_level",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    default_production_register_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("communication_registers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="language_profiles")
    language_variant: Mapped["LanguageVariant"] = relationship(
        back_populates="language_profiles"
    )
    default_production_register: Mapped["CommunicationRegister"] = relationship(
        back_populates="default_for_profiles",
        foreign_keys=[default_production_register_id],
    )
    comprehension_registers: Mapped[list["CommunicationRegister"]] = relationship(
        secondary=language_profile_comprehension_registers,
        back_populates="comprehension_for_profiles",
    )
