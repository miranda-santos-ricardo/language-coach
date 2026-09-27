from app.core.config import Settings


def test_default_database_url_uses_psycopg(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+psycopg://")
