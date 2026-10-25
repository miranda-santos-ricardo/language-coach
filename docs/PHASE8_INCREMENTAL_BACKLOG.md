# Phase 8 — Approved incremental roadmap

## Delivery order and gates

| Sequence | Step | Deliverable | Acceptance |
|---|---|---|---|
| 1 | **8.4.1a** | Authenticated learner identity boundary design and isolated tests | Missing/invalid bearer rejected in secure mode; identity cannot be spoofed via path/header/body; no paid LLM calls; existing development baseline characterized. |
| 2 | **8.4.1b** | Apply identity ownership checks to user/profile/session/turn routes | Cross-user read/write/voice/turn access denied at API entry; resource enumeration protected; all existing tests examined for intentional compatibility impact. |
| 3 | **8.4.1c** | Connect frontend auth and real OIDC test environment | JWT validated server-side; end-user flow uses verified identity; mobile network/same-origin/CORS tested. |
| 4 | **8.2** | Improve scenario selection, recoverable practice and error UX | Text/voice/resume success; deterministic Vitest and manual scripts. |
| 5 | **8.3** | Feedback rendering aligned to existing evaluation schemas | Clear provenance, citations/evidence, abstention, no certified CEFR/phonetical claims. |
| 6 | **8.4.2–8.4.4** | Consent, retention, usage caps, operator restrictions, kill switch | Fail-closed enforced; consent withdrawal and limits tested; admin auditing. |
| 7 | **8.5** | Independent multilingual human-review protocol and execution | Qualified independent judgments; disagreement reconciliation; only measured claims. |
| 8 | **8.6** | Privacy-minimizing telemetry and API budget reporting | Latency/error/cost observations without storing raw tokens or unnecessary audio. |
| 9 | **8.7** | Controlled pilot with recorded manual acceptance evidence | FR-CA/EN everyday and professional; voice/text; fault recovery; mobile. |
| 10 | **8.8** | Architecture/evidence closure and decision | Distinguish technical, pilot and production readiness. |

## Detailed design — next increment 8.4.1a

**Goal:** introduce an isolated, reusable, fail-closed identity dependency for *ordinary learner routes*, explicitly separate from `conversation:assess` privilege.

**Existing interfaces to inspect and reuse:** `backend/app/api/conversation_assessment_auth.py`, `backend/app/services/assessment_oidc_verifier.py`, `backend/app/api/router.py`, `backend/app/main.py`, `backend/app/core/config.py`, `frontend/src/api/client.ts`, `backend/tests/test_conversation_assessment_auth.py` and `test_authenticated_assessment_integration.py`.

**Scope included:** authentication contract, verified-identity type or shared adapter, explicit secure/development mode config, unit tests for missing/malformed/expired/wrong-scope token and forged user ID, API route inventory and impact analysis. API changes to main learner routes **only after dependency behavior and frontend integration strategy are agreed and tested**.

**Excluded:** inventing an OAuth login flow; issuing tokens; bypassing cryptographic validation; enabling any assessment endpoint; adding cloud services; storing bearer tokens in logs; migrating DB solely for auth work.

**Tests:** unit tests with deterministic fake verifier (only for contracts), real-provider validation separately before pilot, regression suite `pytest`, `npm test`, `npm run build`; manual localhost and remote-phone checks after secure integration. Verify existing developer UX is not silently broken.

**Acceptance:** secure configuration rejects missing/unverified tokens; identity derives from verifier, not arbitrary user inputs; pilot cannot start with verifier absent; mode selection explicit and covered by tests; no experimental feature activation; documented changes and test outcomes. No advancement to 8.4.1b until tests are reported and approved.

## PowerShell baseline capture (project root)

```powershell
cd backend
python -m pytest -q
python -m alembic heads
cd ../frontend
npm test -- --run
npm run build
```

Run database-dependent concurrency tests separately with a configured throwaway PostgreSQL database and explicit `ASSESSMENT_TEST_POSTGRES_URL`; do not claim tests passed when skipped. Preserve run logs and note command, environment, commit SHA and timestamp.
