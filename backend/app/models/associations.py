from sqlalchemy import Column, ForeignKey, Integer, Table, Uuid

from app.db.base import Base

language_profile_comprehension_registers = Table(
    "language_profile_comprehension_registers",
    Base.metadata,
    Column(
        "language_profile_id",
        Uuid(as_uuid=True),
        ForeignKey("language_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "communication_register_id",
        Integer,
        ForeignKey("communication_registers.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)
