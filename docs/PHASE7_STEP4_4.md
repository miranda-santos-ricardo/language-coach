# Phase 7 — Step 4.4: Evidence-Based Fluency Feedback

## Scope
Deterministic, localized feedback over **Step 4.3** `FluencyObservation` for `fr-CA`, `en-CA`, `en-US`, `en-GB`; two contexts (`professional`, `conversational`). Internal pure Python service, no new dependencies, no migrations or API endpoints.

## Evidence policy
- VAD intervals indicate **likely** speech, not calibrated ground truth.
- Present descriptive duration and pauses, never fluency/CEFR scores, language diagnoses, accent judgments, or normative speaking-speed thresholds.
- Pauses may be rhetorical, natural, or intentional. A suggested optional exercise is not framed as remediation.
- `INSUFFICIENT_EVIDENCE` suppresses exercise suggestions and timing claims.
- No transcription or raw audio is accepted, logged or persisted.
- `minimum_pause_ms` is applied to raw gaps (not simply reusing filtered pauses); default 200 ms.
- `FluencyObservation` is generated only after recording-specific consent, with user/session ownership enforced **upstream**.

## Files
- `backend/app/services/fluency_feedback.py` (new)
- `backend/tests/test_fluency_feedback.py` (new)

## Validation
```powershell
cd backend
python -m pytest -q tests/test_fluency_feedback.py
python -m pytest -q
alembic current
```

Current baseline provided by user: **501 passing backend tests**, Alembic `c5202601 (head)`. Add test count from this patch to derive expected full suite total. Real-world VAD calibration, conversational API integration, persistence and UI are **not** covered.
