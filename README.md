# language-coach# AI Language & Professional Communication Coach

AI-powered language learning and professional communication coaching platform.

The application is being developed incrementally, with an initial focus on **French** and **English**, while keeping the architecture extensible to additional languages, regional variants, communication registers, and learning modes.

The current implementation focuses on the foundational backend architecture and the domain model required to represent users and their language learning profiles.

---

## Current Status

**Phase 2 — User + Language Profile**

Current implementation milestone:

```text
Phase 1 / Foundation
        ✅ Minimal backend foundation

Phase 2
        ✅ Domain model design
        ✅ SQLAlchemy models
        ⏳ Alembic schema migration
        ⏳ Reference data
        ⏳ Pydantic schemas
        ⏳ Repositories / services
        ⏳ REST API
        ⏳ Backend integration tests
        ⏳ Frontend
```

The database schema has **not yet been migrated**.

The SQLAlchemy models are currently defined and tested, and Alembic is configured to discover their metadata.

---

# Architecture

Current backend architecture:

```text
backend/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── app/
│   ├── api/
│   │   ├── health.py
│   │   └── router.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   │
│   ├── models/
│   │   ├── associations.py
│   │   ├── communication_register.py
│   │   ├── enums.py
│   │   ├── language.py
│   │   ├── language_profile.py
│   │   ├── language_variant.py
│   │   ├── mixins.py
│   │   └── user.py
│   │
│   └── main.py
│
├── tests/
│   ├── test_config.py
│   ├── test_health.py
│   └── test_models.py
│
├── .env.example
├── alembic.ini
└── pyproject.toml
```

The repository root also contains:

```text
compose.yaml
```

for running PostgreSQL locally.

---

# Technology Stack

Current backend stack:

- Python
- FastAPI
- SQLAlchemy 2.x
- PostgreSQL
- Psycopg 3
- Alembic
- Pydantic Settings
- Pytest
- Docker Compose

The backend