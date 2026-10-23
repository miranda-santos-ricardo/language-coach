# Phase 7 — Step 5.4b.1: Voice Text Provenance Compatibility

## Decision
Do not reject committed voice text solely because the application cannot determine whether the user edited the STT transcript. Treat the persisted `ConversationTurn.learner_text` as **confirmed text**, with origin `VOICE_TEXT_UNKNOWN`; evaluate textual communication only. No speech-fidelity, phonetic, pronunciation, acoustic or actual spoken-word claims are permitted.

## Files
- **Updated:** `app/services/conversational_evidence.py` — extends `TextOrigin` with `VOICE_TEXT_UNKNOWN`; invalid combination `stt_original_available=True` is rejected.
- **Updated:** `app/services/sqlalchemy_turn_resolver.py` — fallback for voice turns lacking an authoritative provenance record. Invalid explicit provenance still fails closed; SQL owner filter unchanged.
- **Updated:** `app/services/controlled_conversational_evaluator.py` — explicit no-spoken-fidelity instruction for unknown voice origin.
- **Updated:** `app/services/professional_communication_rubrics.py` — reviewer guidance updated.
- **Updated:** `tests/test_sqlalchemy_turn_resolver.py` — **one intentionally changed expectation**: no metadata for voice now returns UNKNOWN instead of rejecting. The invalid-provider test continues to reject false provenance.
- **New:** `tests/test_voice_text_provenance_compatibility.py` — 13 acceptance tests covering unknown, known, forbidden flags and SQL ownership.

## Security
1. Do not read user identity, text or origin from a client request to build the trusted snapshot.
2. `VOICE_TEXT_UNKNOWN` means only that the confirmed text followed the voice input path; never that STT was accurate or unedited.
3. A trusted provenance callback may later return `STT_UNEDITED` or `USER_EDITED`; unverified values cannot claim an STT original.
4. Inference is restricted to **text**, not articulation, intelligibility, accent, audio, pronunciation or speaking proficiency.
5. This increment changes neither schema nor endpoint. No migration is required.
6. Original transcription fidelity must be supported separately by explicit authoritative provenance and audio evidence; provider messages alone cannot prove speech fidelity.

## Validation
From `backend`:

```powershell
python -m pytest -q tests/test_voice_text_provenance_compatibility.py tests/test_sqlalchemy_turn_resolver.py
python -m pytest -q
alembic current
```

Expect **23 tests** in the combined targeted command (13 new + 10 revised existing) and **706 total** in the full suite if the previously verified 693 tests are present and the 13 tests are newly added. The total remains 706 despite changes to one existing expectation.

## Outstanding work
Real FastAPI auth dependency and request-scoped resolver wiring, durable idempotency, live provider integration, persisted provenance for future voice turns, and production privacy/authorization validation.
