from app.core.config import get_settings


def test_default_database_url_uses_psycopg() -> None:
    settings = get_settings()

    assert settings.database_url.startswith("postgresql+psycopg://")
