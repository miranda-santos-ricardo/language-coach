# Phase 7 — Step 1: Speech Assessment Domain & Evidence Contracts

## Scope
Additive **domain-contract skeleton only**. No routes, model provider, database migration, UI, paid calls, or audio storage are activated. Existing Phase 1–6 API schemas remain unchanged.

## Key decisions
- Original audio, STT transcript, and manually submitted text are distinct entities.
- The recording attempt is identified independently of a conversation-turn ID.
- Evidence distinguishes `MEASURED`, `MODEL_JUDGMENT`, and `HUMAN_REVIEWED`.
- Missing or unreliable assessment is represented by explicit statuses, never invented scores.
- Acoustic dimensions require linked `AUDIO` evidence and audio provenance.
- Audio persistence is off by default; an explicit retention mode requires recorded consent.
- UUID storage references are opaque identifiers; no frontend-provided filesystem paths or provider URLs.
- The speech assessment is conceptually asynchronous/failure-isolated from existing conversation submission; no queue is introduced yet.

## Deferred until Step 2 / dedicated integration decision
1. Inspect and benchmark actual audio decoding and VAD; avoid treating VAD as phoneme assessment.
2. Decide whether a single uploaded Blob can be safely shared across transcription and assessment or needs a short-lived authorized staging resource.
3. Design authorized REST endpoints and lifecycle error handling based on existing API router code.
4. Design SQLAlchemy model/Alembic migration only after confirming latest migration head and ownership joins.
5. Decide replay/retention lifecycle for browser Blob and temporary backend files.
6. Design temporal-measurement tolerances and human-reference corpus; scores are not enabled in Step 1.

## Validation
From `backend/` with existing dependencies installed:

```bash
python -m pytest -q tests/test_speech_assessment_contract.py
python -m pytest -q
alembic current
```

From `frontend/`:

```bash
npm test
npm run build
```

No modifications in this patch to frontend, Alembic or legacy endpoints. Run full regressions on the user's repository before declaring acceptance.

## Limitations
- A full clone was unavailable in the authoring environment. Contracts were aligned with inspected public `app.schemas` modules and tested in isolation.
- Consent validation in the schema alone is not consent auditing; persisted consent must be designed at the API/service boundary.
- Assessment identity and evidence references must be ownership-checked by a future service; Pydantic does not enforce database ownership.
- `score` ranges are representational only and do not mean calibrated scores are available.
