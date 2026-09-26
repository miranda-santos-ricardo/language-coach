from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import language_profile_comprehension_registers
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.language_profile import LanguageProfile


class CommunicationRegister(TimestampMixin, Base):
    """Reference register and the modes in which it can be practiced.

    Capability flags do not define a learner default. A register may be valid
    for production, comprehension, or both; the LanguageProfile stores the
    learner's default production register and a future Session chooses what is
    practiced at a specific moment.
    """
    __tablename__ = "communication_registers"
    __table_args__ = (
        CheckConstraint(
            "production_allowed OR comprehension_allowed",
            name="usable_for_at_least_one_mode",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    production_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    comprehension_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    default_for_profiles: Mapped[list["LanguageProfile"]] = relationship(
        back_populates="default_production_register",
        foreign_keys="LanguageProfile.default_production_register_id",
        passive_deletes=True,
    )
    comprehension_for_profiles: Mapped[list["LanguageProfile"]] = relationship(
        secondary=language_profile_comprehension_registers,
        back_populates="comprehension_registers",
    )
