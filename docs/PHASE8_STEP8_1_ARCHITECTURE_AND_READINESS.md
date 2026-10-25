# Phase 8 — Step 8.1 Architecture & Pilot Readiness Assessment

Status: **ARCHITECTURE APPROVED; PILOT NOT AUTHORIZED**  
Evidence basis: `language-coach-phase7.zip` supplied by the project owner.  
Method: static source inspection; no inference that unit tests have been executed against the owner's database or identity provider.

## 1. Decision

**ADR-8.1-01 — Retain the modular FastAPI + React + PostgreSQL architecture.** No separate services or rewrite are justified for the controlled pilot. Reuse existing practice, conversational feedback, speech and Phase 7 assessment contracts. Maintain experimental assessment routes **disabled by default**.

**ADR-8.1-02 — Protect the main learner API before any multi-user pilot.** The default app registers ordinary user/profile/practice/conversation routes through `app/api/router.py`. Those paths accept a `user_id` in the URL and do not depend on a cryptographically verified principal. The database ownership checks on subordinate resources do not establish requester identity. This is a release-blocking authorization gap.

**ADR-8.1-03 — Reuse, but do not blindly copy, Phase 7 authentication.** `app/api/conversation_assessment_auth.py` has `VerifiedIdentity` and a host-injected token verification boundary; the hard-coded scope `conversation:assess` is NOT appropriate for every ordinary learner action. Define an independently tested learner identity dependency and scope model; validate issuer/audience/signature/expiry using a real provider for pilot deployment.

**ADR-8.1-04 — Separate developer compatibility from pilot deployment.** The currently unauthenticated local workflow must not silently become a permissible pilot mode. Fail closed when secure pilot configuration is selected but verifier is missing; use explicit configuration with tests for both modes. Do not expose insecure mode over untrusted networks.

**ADR-8.1-05 — No quality claims without humans.** Sixteen synthetic multilingual reference cases and test harness output validate contracts, not measurement accuracy. Require independently reviewed real-language cases and disagreement adjudication before asserting validity.

## 2. Verified inventory

| Layer | Inspected files | Observation |
|---|---|---|
| Entrypoint | `backend/app/main.py`, `backend/app/api/router.py` | Default application mounts conventional routes only; assessment routes are not in this registry. |
| Main learner routes | `backend/app/api/users.py`, `language_profiles.py`, `practice_sessions.py`, `conversation_turns.py` | Path-identified users; no identity authentication dependency in examined handlers. |
| Browser client | `frontend/src/api/client.ts` | JSON fetch wrapper, no bearer-token lifecycle in examined code. |
| Assessment opt-in | `backend/app/api/assessment_secure_activation.py` | Requires enabled flag, GO readiness and concrete `AssessmentOIDCVerifier`; requires runtime operational attestations. |
| Assessment identity | `backend/app/api/conversation_assessment_auth.py`, `conversation_assessment_persistent.py` | Verifier-injected Bearer identity, owner reauthorization of committed turns. |
| Migrations | `backend/alembic/versions/c5202601_phase5_conversations.py` through `c5202603_assessment_reconciliation_audit.py` | Latest migration filename `c5202603`; live database head not verified. |
| Main UX | `frontend/src/components/ConversationPanel.tsx`, `LanguageFeedbackPanel.tsx`, `VoiceRecorder.tsx`, `ResumePracticeSessions.tsx` | Existing conversational and audio UI to retain. |
| Linguistic assessment | `backend/app/services/pronunciation_assessment.py`, `fluency_temporal.py`, `controlled_conversational_evaluator.py`, `conversational_evidence.py` | Experimental services exist; no empirical accuracy conclusion. |
| PostgreSQL race tests | `backend/tests/test_postgres_assessment_concurrency.py` | Environment-dependent integration tests; actual successful execution not established. |
| Operating defaults | `backend/app/core/config.py`, `backend/app/main.py` | Permissive wildcard CORS and an embedded local database connection default in repository; must harden pilot configuration and remove credentials. |

## 3. User journey and pilot boundary

Existing basic journey: user selection → language profile → create/resume practice session → text/voice turn → stored coach response and structured feedback → replay/continuation. Actual end-to-end behavior on external mobile networks, browsers and microphones still requires operational verification.

Target pilot boundary: verified user identity → authorized resource ownership → recorded consent → allowed feature and budget → existing practice services → evidence-backed feedback (or declared abstention) → minimal telemetry. Every assessment activation additionally requires the Phase 7 readiness gate.

## 4. Dependencies and blockers

**P0 / pilot blockers**
1. Authenticate and authorize ordinary learner API, including `/users` enumeration and creation strategy.
2. Establish OIDC verifier / identity-to-local-user mapping with real provider; no client-supplied `user_id` trust.
3. Actually execute PostgreSQL concurrency tests, migrations and isolation checks in an appropriately configured database.
4. Implement consent, retention/deletion, administration protections, rate limits, provider budgets and emergency shutdown.
5. Review CORS, defaults and secret handling; never deploy wildcard access plus unauthenticated data endpoints.

**P1 / validation dependencies**
1. Review current FE contract coverage before adding feedback UI.
2. Run FR-CA and EN human review protocol with independent annotators; no invented results.
3. Capture task-level latency, STT/TTS failures and token/cost telemetry with minimal content retention.
4. Conduct real text, voice and mobile acceptance sessions.

## 5. Gates and status nomenclature

- `TECHNICALLY_VALIDATED`: source changes tested with verifiable automated results.
- `PILOT_READY`: identity, privacy, operational limits, recovery and safety controls validated; documented operator approval.
- `PILOT_VALIDATED`: real-user utility and quality criteria met with recorded evidence.
- `PRODUCTION_READY`: separate production controls and operational evidence validated.

**As of this assessment: architecture approved; no claim to any of the four readiness states.** Static inspection cannot establish runtime control effectiveness.

## 6. Acceptance checklist — Step 8.1

- [x] Inspect repository and map existing major services/routes/components.
- [x] Document Phase 7 capabilities as experimental and identify reuse targets.
- [x] Confirm default routing versus gated experimental assessment mounting.
- [x] Identify main learner authorization gap and isolate P0 risk.
- [x] Propose target architecture and ordered workstreams.
- [x] Establish objective readiness state definitions and release blockers.
- [ ] Execute tests against developer environment, PostgreSQL and provider (required for downstream gates, **not** asserted complete under a static architecture review).

## 7. Exclusions

No application source, migration, endpoint enablement or frontend behavior changed in Step 8.1. No operational readiness claim. No human validation performed.
