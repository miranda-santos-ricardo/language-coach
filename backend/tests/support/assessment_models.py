"""Shared SQLite-only assessment schema. Not production ORM models."""
from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class LanguageVariant(Base):
    __tablename__ = 'language_variants'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String)

class LanguageProfile(Base):
    __tablename__ = 'language_profiles'
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), nullable=False)
    language_variant_id: Mapped[int] = mapped_column(ForeignKey('language_variants.id'))

class PracticeSession(Base):
    __tablename__ = 'practice_sessions'
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    language_profile_id: Mapped[object] = mapped_column(ForeignKey('language_profiles.id'))
    scenario_key: Mapped[str | None] = mapped_column(String, nullable=True)

class ConversationTurn(Base):
    __tablename__ = 'conversation_turns'
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    practice_session_id: Mapped[object] = mapped_column(ForeignKey('practice_sessions.id'))
    client_request_id: Mapped[object] = mapped_column(Uuid(as_uuid=True))
    input_modality: Mapped[str] = mapped_column(String)
    learner_text: Mapped[str] = mapped_column(String)

