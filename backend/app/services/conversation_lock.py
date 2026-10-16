"""Non-blocking, per-practice-session execution gate.

PostgreSQL: transaction-scoped advisory locks work across workers and hosts.
SQLite: in-process fallback for the existing lightweight test environment ONLY.
The service must always commit or roll back to release PostgreSQL locks.
"""
import threading
import uuid
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session


class ConversationBusyError(RuntimeError):
    """A conversation operation is already in flight for this practice session."""


_registry_mutex = threading.Lock()
_local_locks: dict[uuid.UUID, threading.Lock] = {}


def _local_lock(session_id: uuid.UUID) -> threading.Lock:
    with _registry_mutex:
        return _local_locks.setdefault(session_id, threading.Lock())


@contextmanager
def conversation_execution_gate(db: Session, practice_session_id: uuid.UUID) -> Iterator[None]:
    """Serialize submissions before reading history or invoking the provider.

    The caller must own a dedicated SQLAlchemy Session. For PostgreSQL the
    transaction remains open while the LLM runs; this is a documented interim
    compromise until durable request reservations are introduced.
    """
    bind = db.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        # Signed 64-bit key from UUID: only a lock namespace, never an identity check.
        key = (practice_session_id.int & ((1 << 64) - 1))
        if key >= (1 << 63):
            key -= 1 << 64
        acquired = db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key})
        if not acquired:
            # Close the implicit transaction opened by the lock query.
            db.rollback()
            raise ConversationBusyError("A request for this practice session is already processing")
        yield
    elif dialect == "sqlite":
        lock = _local_lock(practice_session_id)
        if not lock.acquire(blocking=False):
            raise ConversationBusyError("A request for this practice session is already processing")
        try:
            yield
        finally:
            lock.release()
    else:
        raise RuntimeError(f"Unsupported conversation locking dialect: {dialect}")
