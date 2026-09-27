# AI Language & Professional Communication Coach

AI-powered language learning and professional communication coaching platform.

The project is being developed incrementally. French and English are the initial languages, with regional variants modeled independently so that additional languages and variants can be added without redesigning the domain.

## Current status

**Phase 2 — User + Language Profile**

Implemented so far:

- FastAPI backend foundation
- centralized configuration
- SQLAlchemy 2.x + Psycopg 3
- PostgreSQL local environment through Docker Compose
- Alembic migration infrastructure
- `GET /health`
- domain models for User, Language, LanguageVariant, CommunicationRegister and LanguageProfile
- CEFR representation (`A1`–`C2`)
- production/comprehension register modeling
- schema migration
- reproducible reference-data migration
- backend structural tests
- Pydantic API schemas for users, languages, communication registers and language profiles
- repositories for users, languages, registers and language profiles
- application services with business-rule validation and explicit write transactions
- REST API for users, languages, communication registers and language profiles
- HTTP error mapping for domain/service failures

Not implemented yet:

- frontend
- Session Context and later AI/voice capabilities

## Repository structure

```text
.
├── compose.yaml
├── README.md
└── backend/
    ├── alembic/
    │   ├── env.py
    │   └── versions/
    │       ├── 0001_phase2_domain_schema.py
    │       └── 0002_phase2_reference_data.py
    ├── app/
    │   ├── api/
    │   ├── core/
    │   ├── db/
    │   ├── models/
    │   ├── repositories/
    │   ├── schemas/
    │   ├── services/
    │   └── main.py
    ├── tests/
    ├── .env.example
    ├── alembic.ini
    └── pyproject.toml
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

For `fr-CA`, `regional_focus` is currently `Québec`.

## Communication registers

Reference data currently includes:

- `professional`
- `formal_executive`
- `everyday`
- `conversational`
- `colloquial`

All five are currently available for both production and comprehension. `colloquial` being available for production does not make it the learner's default; the Language Profile stores the default production register, while a future Session will choose the register practiced at that moment.

## CEFR

Supported levels:

```text
A1
A2
B1
B2
C1
C2
```

The application represents CEFR with a Python `StrEnum`. PostgreSQL stores it as text protected by a CHECK constraint rather than a native PostgreSQL enum.

## Database integrity

The schema currently protects important invariants including:

- unique language codes
- unique variant codes
- variant → language foreign key
- valid CEFR values
- one Language Profile per user + variant
- valid User/Profile/Variant/Register foreign keys
- unique comprehension-register associations through a composite primary key
- reference-data relationships protected with restrictive delete behavior

## API schema contracts

Pydantic schemas now define the API boundary without exposing internal integer IDs for reference data. External contracts use stable codes such as:

```text
fr
fr-CA
professional
```

Language Profile creation is modeled with:

```json
{
  "language_code": "fr",
  "variant_code": "fr-CA",
  "cefr_level": "B2",
  "default_production_register_code": "professional",
  "comprehension_register_codes": [
    "professional",
    "everyday",
    "colloquial"
  ]
}
```

Pydantic validates payload structure, CEFR values, code shape, duplicate comprehension registers and PATCH semantics. Rules that depend on reference data — for example whether `fr-CA` belongs to `fr`, whether a register exists/is active, or whether it supports production — are intentionally deferred to the service layer.

A PATCH may update CEFR/register preferences independently. Changing a variant requires `language_code` and `variant_code` to be supplied together. An empty PATCH or explicit `null` for a patch field is rejected. An empty comprehension-register list is allowed and means "clear the current comprehension selections."


## Repository and service layer

Repositories are responsible only for persistence queries and ORM loading. They never commit transactions. Services orchestrate business rules and own write transactions.

The current service layer enforces rules including:

- user existence before profile operations
- profile ownership scoped by both `user_id` and `profile_id`
- language and variant lookup by stable codes
- language/variant compatibility (`fr-CA` must belong to `fr`)
- active reference-data validation
- register capability validation for production/comprehension
- one Language Profile per user + language variant
- safe profile updates, including duplicate checks when changing variants
- clearing/replacing comprehension registers

Expected application errors remain represented as service exceptions. The REST layer now maps them to HTTP semantics without coupling services to FastAPI.

Write transaction ownership is explicit:

```text
repository → query/add only
service    → business rules + commit/rollback
API        → request/response + HTTP error mapping
```


## REST API

Current endpoints:

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

Relevant HTTP semantics include:

- `201 Created` for user/profile creation
- `404 Not Found` for missing users, owned profiles, and language variant collections requested for an unknown language
- `409 Conflict` when attempting to create a duplicate profile for the same user + variant
- `422 Unprocessable Content` for semantic request errors such as language/variant mismatch, unknown body reference codes, unsupported register modes, or invalid Pydantic payloads

Profile ownership is enforced through the nested user route and the underlying repository query uses both `user_id` and `profile_id`.

`GET /communication-registers` is intentionally exposed so the frontend can discover register options and capability flags from reference data instead of hardcoding them.

## Reference data strategy

Reference data is versioned through Alembic rather than inserted during application startup.

Migration chain:

```text
<base>
  ↓
0001_phase2_schema
  ↓
0002_phase2_reference_data (head)
```

`0001_phase2_schema` creates the Phase 2 database structure.

`0002_phase2_reference_data` inserts the initial languages, language variants and communication registers.

## Local setup

Start PostgreSQL from the repository root:

```powershell
docker compose up -d postgres
```

Then configure the backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Apply migrations:

```powershell
alembic upgrade head
```

Run the API:

```powershell
python -m uvicorn app.main:app --reload
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Tests

Run from `backend/`:

```powershell
pytest -q
```

Current expected result at this milestone:

```text
60 passed
```

Useful Alembic validation commands:

```powershell
alembic heads
alembic current
alembic check
alembic history --verbose
```

The current Alembic head is:

```text
0002_phase2_reference_data
```

## Out of scope for the current milestone

The following are intentionally not implemented yet:

- Session / Session Context
- authentication / OAuth
- microphone / MediaRecorder
- Speech-to-Text / Text-to-Speech
- OpenAI or other LLM integration
- Learning Engine / AI Orchestrator
- conversations / interactions
- mistakes / vocabulary / progress engine
- scenarios / dashboard
- RAG / vector databases / agents
- cloud deployment / realtime voice

## Development principle

The repository is the source of truth. Development proceeds incrementally:

```text
design → implement → test → validate → continue
```

The next implementation step is the REST API layer, which will expose the validated service operations through FastAPI endpoints and map service exceptions to HTTP status codes.
