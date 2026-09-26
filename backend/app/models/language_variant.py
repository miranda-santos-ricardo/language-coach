from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.language import Language
    from app.models.language_profile import LanguageProfile


class LanguageVariant(TimestampMixin, Base):
    __tablename__ = "language_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    language_id: Mapped[int] = mapped_column(
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(35), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    regional_focus: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    language: Mapped["Language"] = relationship(back_populates="variants")
    language_profiles: Mapped[list["LanguageProfile"]] = relationship(
        back_populates="language_variant",
        passive_deletes=True,
    )
