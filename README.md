# AI Language & Professional Communication Coach

AI-powered language learning and professional communication coaching platform.

The project is being developed incrementally. French and English are the initial languages, with regional variants modeled independently so that additional languages and variants can be added without redesigning the domain.

## Current status

**Phase 2 — User + Language Profile**

Implemented so far:

- FastAPI backend foundation and `/health`
- centralized configuration
- SQLAlchemy 2.x + Psycopg 3
- PostgreSQL local environment through Docker Compose
- Alembic migrations and reproducible reference data
- User, Language, LanguageVariant, CommunicationRegister and LanguageProfile domain models
- CEFR (`A1`–`C2`), production/comprehension register modeling and ownership rules
- Pydantic API schemas
- repository/service layers with explicit transaction ownership
- REST API for users, languages, communication registers and language profiles
- React + TypeScript + Vite frontend
- user selection/creation
- language profile visualization
- language profile creation/editing
- frontend backend-health indicator
- local-development CORS configuration

Not implemented yet:

- Session Context
- voice/STT/TTS
- AI orchestration and learning engine
- authentication
- progress/mistake/vocabulary tracking

## Repository structure

```text
.
├── compose.yaml
├── README.md
├── backend/
│   ├── alembic/
│   │   └── versions/
│   │       ├── 0001_phase2_domain_schema.py
│   │       └── 0002_phase2_reference_data.py
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── tests/
│   ├── .env.example
│   ├── alembic.ini
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── api/
    │   ├── components/
    │   ├── test/
    │   ├── App.tsx
    │   └── main.tsx
    ├── .env.example
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    └── vite.config.ts
```

## Domain model

```text
User
 │
 │ 1:N
 ▼
LanguageProfile
 │
 ├──────────────► LanguageVariant ──N:1──► Language
 │
 ├──────────────► CommunicationRegister
 │                 default production register
 │
 └────── N:M ──► CommunicationRegister
                   comprehension registers
```

A user may have multiple Language Profiles, but only one profile for each language variant:

```text
UNIQUE(user_id, language_variant_id)
```

A Language Profile stores the learner's persistent baseline for a language variant. A future Session will represent what is being practiced at a specific moment. Therefore the same `fr-CA` profile can later be used for Professional practice one day and Colloquial practice another day.

## Regional variants

Reference data currently includes:

```text
French
├── fr-CA — French — Canada / Québec
└── fr-FR — French — France

English
├── en-CA — English — Canada
├── en-US — English — United States
└── en-GB — English — United Kingdom
```

For `fr-CA`, `regional_focus` is `Québec`.

## Communication registers

Reference data currently includes:

- `professional`
- `formal_executive`
- `everyday`
- `conversational`
- `colloquial`

All five are currently available for both production and comprehension. `colloquial` being available for production does not make it the learner's default; the Language Profile stores the default production register, while a future Session will choose the register practiced at that moment.

## REST API

```text
GET    /health

POST   /users
GET    /users
GET    /users/{user_id}

GET    /languages
GET    /languages/{language_code}/variants

GET    /communication-registers

POST   /users/{user_id}/language-profiles
GET    /users/{user_id}/language-profiles
GET    /users/{user_id}/language-profiles/{profile_id}
PATCH  /users/{user_id}/language-profiles/{profile_id}
```

Reference data is exposed by stable codes (`fr`, `fr-CA`, `professional`) instead of internal integer IDs.

## Frontend

The Phase 2 frontend is intentionally small and functional. It supports:

```text
Who's practicing?
├── select an existing user
└── create a user

Selected user
└── Languages
    ├── view Language Profiles
    ├── add Language Profile
    └── edit Language Profile
```

The Language Profile form reads languages, variants and communication registers from the backend instead of hardcoding them.

The form supports:

- language
- regional variant
- CEFR
- default production/speaking register
- multiple comprehension registers

For example, a single `fr-CA` profile may have Professional as its default production register while including Professional, Everyday, Conversational and Colloquial in comprehension.

The frontend does not implement Session behavior. Choosing the register being practiced *today* belongs to the future Session Context phase.

## Technology stack

Backend:

- FastAPI
- SQLAlchemy 2.x
- PostgreSQL
- Psycopg 3
- Alembic
- Pydantic
- Pytest

Frontend:

- React 19
- TypeScript
- Vite 8
- native `fetch` API
- Vitest + React Testing Library

No frontend state-management or UI-component framework has been added because Phase 2 does not require one yet.

## Local setup

### 1. PostgreSQL

From the repository root:

```powershell
docker compose up -d postgres
```

### 2. Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

### 3. Frontend

Use a Node.js version compatible with Vite 8 (Node 20.19+ or 22.12+).

In another terminal:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

Default frontend API configuration:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The backend permits the local Vite development origins configured in `CORS_ORIGINS`.

## Tests

Backend:

```powershell
cd backend
pytest -q
alembic check
```

Current expected backend result at this milestone:

```text
62 passed
```

Frontend:

```powershell
cd frontend
npm test
npm run build
```

Current frontend suite contains 5 tests covering the important Phase 2 user flows: backend status, user selection/creation, data-driven language-profile form, profile creation request and profile editing.

## Migration chain

```text
<base>
  ↓
0001_phase2_schema
  ↓
0002_phase2_reference_data (head)
```

There is no frontend-related database migration. `alembic check` should continue to report no new upgrade operations.

## Out of scope

The following remain intentionally outside Phase 2:

- Session / Session Context
- microphone and audio upload
- Speech-to-Text / Text-to-Speech
- OpenAI or other LLM integration
- conversations/interactions
- mistakes and vocabulary
- scenarios and progress engine
- authentication/OAuth
- cloud deployment
- RAG/vector databases/agents

## Next milestone

After Step 10 is validated locally, the remaining Phase 2 work is end-to-end validation and final handoff/documentation before beginning **Phase 3 — Session Context**.
