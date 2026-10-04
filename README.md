# AI Language & Professional Communication Coach

A local-first AI-powered language learning and professional communication platform focused initially on **Canadian French (fr-CA)** and **English (en-CA)**.

The project is designed not only for general language practice, but also for **professional and corporate communication**, including formal communication, executive language, vocabulary, tone, persuasion, and communication scenarios relevant to environments such as banking, insurance, consulting, technology, and other professional settings.

The application is being developed incrementally, with each phase introducing a new architectural capability while preserving compatibility with the previous phases.

---

## Project Status

The project has completed the foundational user, language-profile, and practice-session capabilities.

Phase 4 is currently introducing the application's first real **voice interaction cycle**.

### Current progress

| Phase | Capability | Status |
|---|---|---|
| Phase 1 | Application Foundation | ✅ Completed |
| Phase 2 | User + Language Profile | ✅ Completed |
| Phase 3 | Practice Session Lifecycle | ✅ Completed |
| Phase 4 | Voice Input + Speech-to-Text | 🚧 In Progress |
| Phase 5+ | Conversational AI / Coaching | 📋 Planned |

Current backend regression:

```text
133 tests passed
0 warnings
```

No real OpenAI API calls are performed by the automated test suite.

---

# Current Architecture

The application currently follows a layered architecture:

```text
┌─────────────────────────────────────┐
│          React Frontend             │
│                                     │
│  User Selection                     │
│  Language Profile                   │
│  Practice Session                   │
│  Voice Recording (Phase 4)          │
└──────────────────┬──────────────────┘
                   │ HTTP / JSON
                   │ multipart/form-data
                   ▼
┌─────────────────────────────────────┐
│             FastAPI                 │
│                                     │
│  REST API                           │
│  Upload Validation                  │
│  Error Mapping                      │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│           Service Layer             │
│                                     │
│  UserService                        │
│  LanguageProfileService             │
│  PracticeSessionService             │
│  TranscriptionService               │
└──────────────┬───────────┬──────────┘
               │           │
               ▼           ▼
┌───────────────────┐  ┌────────────────────┐
│ Repository Layer  │  │ SpeechToText       │
│                   │  │ abstraction        │
│ SQLAlchemy        │  └─────────┬──────────┘
└─────────┬─────────┘            │
          │                      ▼
          ▼             ┌────────────────────┐
┌───────────────────┐   │ OpenAI STT         │
│ PostgreSQL        │   │ Integration        │
└───────────────────┘   └────────────────────┘
```

The frontend does not know which Speech-to-Text provider is being used.

Provider-specific behavior remains behind the backend `SpeechToText` abstraction.

---

# Phase 1 — Application Foundation

Phase 1 established the technical foundation of the application.

Core technologies include:

### Backend

- Python 3.12+
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic
- Pytest

### Frontend

- React
- TypeScript
- Vite
- Vitest
- React Testing Library

The initial architecture established clear separation between:

```text
API
 ↓
Service
 ↓
Repository
 ↓
Database
```

---

# Phase 2 — User + Language Profile

Phase 2 introduced persistent users and language-learning profiles.

A user can maintain language profiles containing information such as:

- language
- language variant
- CEFR level
- target CEFR level
- communication register
- learning preferences

Initial language support includes:

```text
French
 ├── fr-CA
 └── fr-FR

English
 ├── en-CA
 ├── en-US
 └── en-GB
```

The architecture is designed so additional languages and variants can be introduced without redesigning the application.

---

# Phase 3 — Practice Session Lifecycle

Phase 3 introduced the concept of a **PracticeSession**.

A session represents a language-learning interaction associated with a specific language profile.

The ownership hierarchy is:

```text
User
 └── LanguageProfile
       └── PracticeSession
```

The backend validates this hierarchy before accessing a session.

A practice session includes contextual information such as:

- training mode
- communication register
- current CEFR level
- target CEFR level
- effective CEFR level
- language
- language variant
- scenario
- lifecycle status

Supported lifecycle states include:

```text
ACTIVE
COMPLETED
ABANDONED
```

Only active sessions can participate in new interactions.

Phase 3 established the session context required for the conversational capabilities introduced in later phases.

---

# Phase 4 — Voice Input + Speech-to-Text

Phase 4 introduces the first real voice interaction cycle.

The target flow is:

```text
User
 ↓
Browser Microphone
 ↓
MediaRecorder
 ↓
Audio Blob
 ↓
multipart/form-data
 ↓
FastAPI
 ↓
Audio Validation
 ↓
PracticeSession Validation
 ↓
TranscriptionService
 ↓
SpeechToText
 ↓
OpenAI STT
 ↓
Transcript
 ↓
React UI
```

Phase 4 deliberately stops at transcription.

The following capabilities are **not part of Phase 4**:

- LLM conversation
- grammar correction
- communication coaching
- AI-generated responses
- Text-to-Speech
- pronunciation scoring
- conversation history
- realtime WebSocket/WebRTC communication

Those capabilities will be introduced in later phases.

---

## Phase 4 Progress

### Step 1 — Repository Inspection

✅ Completed

The existing architecture and Phase 3 implementation were reviewed before introducing voice functionality.

---

### Step 2 — Voice/STT Architecture

✅ Completed

The Speech-to-Text architecture was defined before implementation.

The key design principle is provider isolation:

```text
TranscriptionService
        │
        ▼
SpeechToText
   Protocol
        │
        ▼
OpenAISpeechToText
```

This allows the STT provider to be replaced later without changing the application service layer.

---

### Step 3 — OpenAI STT Integration

✅ Completed

The backend now contains an isolated OpenAI Speech-to-Text integration.

Configuration is environment-based:

```dotenv
OPENAI_API_KEY=
OPENAI_STT_MODEL=gpt-transcribe
OPENAI_STT_TIMEOUT_SECONDS=30
```

The API key exists only in the backend.

It must never be exposed to the React application.

Locale normalization is handled by the backend.

Example:

```text
fr-CA → fr
fr-FR → fr

en-CA → en
en-US → en
en-GB → en
```

The language is derived from the `PracticeSession` context rather than supplied by the frontend.

---

### Step 4 — Transcription Service

✅ Completed

`TranscriptionService` coordinates the transcription use case.

Responsibilities include:

```text
User ownership
      ↓
LanguageProfile ownership
      ↓
PracticeSession ownership
      ↓
Session must be ACTIVE
      ↓
Resolve language variant
      ↓
Normalize STT language
      ↓
SpeechToText.transcribe()
      ↓
TranscriptionResult
```

The service does not depend directly on OpenAI.

Instead, it depends on the `SpeechToText` interface.

This makes the service independently testable.

---

### Step 5 — Audio Upload API

✅ Completed

The FastAPI backend now accepts audio through:

```text
multipart/form-data
```

The transcription route follows the existing resource hierarchy:

```text
/users/{user_id}
/language-profiles/{profile_id}
/sessions/{practice_session_id}
/transcriptions
```

Audio is validated before reaching the STT provider.

Validation currently includes:

- empty audio detection
- supported MIME type
- upload size limit
- filename handling

Maximum upload size is configurable:

```dotenv
MAX_AUDIO_UPLOAD_BYTES=10485760
```

Audio is processed in memory and is **not persisted**.

Transcripts are also not persisted during this phase.

No database migration was required for Phase 4.

---

### Step 6 — Backend Tests

✅ Completed

The Phase 4 backend is covered by unit and API tests.

Current regression result:

```text
133 passed
```

Coverage introduced during this phase includes:

#### Audio validation

- WebM
- MP4
- MPEG
- WAV
- empty audio
- missing MIME
- unsupported MIME
- maximum-size boundary
- oversized uploads
- fallback filename

#### Multipart transcription API

Tests verify:

```text
multipart upload
      ↓
FastAPI
      ↓
audio validation
      ↓
TranscriptionService
      ↓
TranscriptionResult
```

The API tests use fake transcription services.

No real OpenAI request is performed.

#### Error mapping

The HTTP contract currently includes:

| Condition | HTTP |
|---|---:|
| Empty audio | `400` |
| User/Profile/Session not found | `404` |
| Inactive PracticeSession | `409` |
| Audio too large | `413` |
| Unsupported audio type | `415` |
| Invalid multipart request | `422` |
| STT configuration unavailable | `503` |
| STT rate limit | `503` |
| STT provider failure | `503` |
| STT timeout | `504` |

Internal provider information and API configuration details are not exposed to clients.

---

## Remaining Phase 4 Work

The backend portion of the first voice cycle is now complete.

Remaining work is primarily in the React frontend:

```text
Step 7
Browser Audio Recording
        ↓
getUserMedia()
        ↓
MediaRecorder
        ↓
Audio Blob

Step 8
Audio Upload Integration
        ↓
FormData
        ↓
FastAPI

Step 9
Voice Interaction UX
        ↓
IDLE
RECORDING
RECORDED
UPLOADING
TRANSCRIBING
SUCCESS
ERROR

Step 10
Frontend Tests

Step 11
Real French / English STT Validation

Step 12
Integration / E2E
        ↓
Phase 4 Closure
```

---

# Voice Recording Design

The frontend will use native browser APIs rather than a heavy audio library:

```text
navigator.mediaDevices.getUserMedia()
                ↓
           MediaStream
                ↓
          MediaRecorder
                ↓
            chunks[]
                ↓
              Blob
```

MIME support will be determined using:

```typescript
MediaRecorder.isTypeSupported(...)
```

The browser recording layer will not contain OpenAI-specific logic.

---

# Security Principles

The project follows several security boundaries.

### API credentials

`OPENAI_API_KEY` exists only on the backend.

Never place provider credentials in:

```text
frontend/.env
VITE_*
React source code
Git
browser storage
API responses
logs
```

### Audio

Audio is currently:

```text
received
   ↓
validated
   ↓
transcribed
   ↓
discarded
```

Raw audio is not stored.

### Transcript

During Phase 4, transcripts are returned to the frontend but are not persisted.

### Ownership

Every transcription belongs to:

```text
User
 ↓
LanguageProfile
 ↓
PracticeSession
```

A session belonging to another profile or user must not be usable for transcription.

---

# Testing Strategy

The project favors isolated tests and explicit architectural boundaries.

The STT provider is replaced by fakes during automated tests:

```text
Production

TranscriptionService
        ↓
OpenAISpeechToText
        ↓
OpenAI


Tests

TranscriptionService
        ↓
FakeSpeechToText
```

This provides:

- deterministic tests
- no external API dependency
- no API cost during testing
- faster execution
- controlled error simulation

Current backend status:

```text
133 passed
0 warnings
0 real OpenAI calls
```

---

# Environment Configuration

Example backend environment configuration:

```dotenv
DATABASE_URL=postgresql+psycopg://...

OPENAI_API_KEY=
OPENAI_STT_MODEL=gpt-transcribe
OPENAI_STT_TIMEOUT_SECONDS=30

MAX_AUDIO_UPLOAD_BYTES=10485760
```

Use the repository's `.env.example` as the configuration reference.

Never commit the real `.env` file.

---

# Running the Backend

From the backend directory:

```bash
uvicorn app.main:app --reload
```

Run tests with:

```bash
pytest
```

Current expected backend regression:

```text
133 passed
```

---

# Running the Frontend

From the frontend directory:

```bash
npm install
npm run dev
```

Run frontend tests with:

```bash
npm test
```

Create a production build with:

```bash
npm run build
```

---

# Local Network Development

The application is designed to run locally during its initial development phases.

The backend and frontend may be exposed on the local network for testing from another device.

However, browser microphone access has additional security requirements.

`getUserMedia()` generally requires a **secure browser context**.

While:

```text
http://localhost
```

is treated specially by browsers, accessing the application through a LAN address such as:

```text
http://192.168.x.x
```

may prevent microphone access.

Changing CORS to:

```text
*
```

does not solve this requirement.

Local HTTPS may therefore be required when testing microphone recording from a phone or another device on the LAN.

CORS and browser secure-context requirements should be treated as separate concerns.

---

# Development Principles

The project follows several architectural principles:

1. **Local-first development**
2. **Incremental delivery**
3. **Explicit service boundaries**
4. **Provider isolation**
5. **Backend-controlled AI credentials**
6. **Session-based learning context**
7. **Testability before provider integration**
8. **No unnecessary framework abstractions**
9. **No premature persistence**
10. **No premature realtime architecture**

The project intentionally uses the simplest architecture capable of supporting the current phase.

---

# Technology Stack

## Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
PostgreSQL
OpenAI Python SDK
Pytest
```

## Frontend

```text
React
TypeScript
Vite
Vitest
React Testing Library
Browser Media APIs
```

## AI

Current:

```text
OpenAI Speech-to-Text
```

Future phases are expected to introduce conversational AI and communication coaching behind similarly isolated service boundaries.

---

# Roadmap

The long-term direction is to evolve the application from:

```text
Language Profile
      ↓
Practice Session
      ↓
Voice
      ↓
Transcript
```

tow