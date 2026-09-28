import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CEFRLevel, SessionStatus, TrainingMode
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.communication_register import CommunicationRegister
    from app.models.language_profile import LanguageProfile


class PracticeSession(TimestampMixin, Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        CheckConstraint(
            """
            (
                status = 'active'
                AND ended_at IS NULL
            )
            OR
            (
                status IN ('completed', 'abandoned')
                AND ended_at IS NOT NULL
            )
            """,
            name="status_matches_ended_at",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ended_at_not_before_started_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    language_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "language_profiles.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    training_mode: Mapped[TrainingMode] = mapped_column(
        Enum(
            TrainingMode,
            name="training_mode",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    communication_register_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "communication_registers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    profile_cefr_snapshot: Mapped[CEFRLevel] = mapped_column(
        Enum(
            CEFRLevel,
            name="profile_cefr_snapshot",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    target_cefr: Mapped[CEFRLevel | None] = mapped_column(
        Enum(
            CEFRLevel,
            name="target_cefr",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )

    scenario_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[SessionStatus] = mapped_column(
        Enum(
            SessionStatus,
            name="session_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=SessionStatus.ACTIVE,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    language_profile: Mapped["LanguageProfile"] = relationship(
        back_populates="practice_sessions",
    )

    communication_register: Mapped["CommunicationRegister"] = relationship(
        back_populates="practice_sessions",
    )

    @property
    def effective_cefr(self) -> CEFRLevel:
        return self.target_cefr or self.profile_cefr_snapshot