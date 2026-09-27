from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import CommunicationRegister, Language, LanguageVariant


@pytest.fixture
def service_session() -> Generator[Session, None, None]:
    """Isolated DB for repository/service/API behavior tests.

    Application schema creation remains Alembic-only. ``create_all`` is used
    here solely to build a disposable in-memory test database from the already
    migration-validated SQLAlchemy metadata.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionFactory() as session:
        _seed_reference_data(session)
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def api_client(service_session: Session) -> Generator[TestClient, None, None]:
    from app.db.session import get_db
    from app.main import app

    def override_get_db() -> Generator[Session, None, None]:
        yield service_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _seed_reference_data(session: Session) -> None:
    french = Language(code="fr", name="French", is_active=True)
    english = Language(code="en", name="English", is_active=True)
    session.add_all([french, english])
    session.flush()

    session.add_all(
        [
            LanguageVariant(
                language_id=french.id,
                code="fr-CA",
                display_name="French — Canada / Québec",
                country_code="CA",
                regional_focus="Québec",
                is_active=True,
            ),
            LanguageVariant(
                language_id=french.id,
                code="fr-FR",
                display_name="French — France",
                country_code="FR",
                regional_focus=None,
                is_active=True,
            ),
            LanguageVariant(
                language_id=english.id,
                code="en-CA",
                display_name="English — Canada",
                country_code="CA",
                regional_focus=None,
                is_active=True,
            ),
            LanguageVariant(
                language_id=english.id,
                code="en-US",
                display_name="English — United States",
                country_code="US",
                regional_focus=None,
                is_active=True,
            ),
            LanguageVariant(
                language_id=english.id,
                code="en-GB",
                display_name="English — United Kingdom",
                country_code="GB",
                regional_focus=None,
                is_active=True,
            ),
        ]
    )

    session.add_all(
        [
            CommunicationRegister(
                code="professional",
                display_name="Professional",
                production_allowed=True,
                comprehension_allowed=True,
                is_active=True,
            ),
            CommunicationRegister(
                code="formal_executive",
                display_name="Formal / Executive",
                production_allowed=True,
                comprehension_allowed=True,
                is_active=True,
            ),
            CommunicationRegister(
                code="everyday",
                display_name="Everyday",
                production_allowed=True,
                comprehension_allowed=True,
                is_active=True,
            ),
            CommunicationRegister(
                code="conversational",
                display_name="Conversational",
                production_allowed=True,
                comprehension_allowed=True,
                is_active=True,
            ),
            CommunicationRegister(
                code="colloquial",
                display_name="Colloquial",
                production_allowed=True,
                comprehension_allowed=True,
                is_active=True,
            ),
        ]
    )
    session.commit()
