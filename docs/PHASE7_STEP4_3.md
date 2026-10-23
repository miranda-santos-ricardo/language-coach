# Phase 7 — Step 4.3: Fluency Temporal Runtime Integration

## Scope
Adds an *internal*, opt-in orchestration function joining the real/local Silero VAD adapter (`compare_speech_vad` from Step 4.2) to the validated temporal calculator (`calculate_temporal_metrics` from Step 4.1). Does not change HTTP endpoints, DB schema, conversational flow, or frontend. No new dependencies; the real Silero runtime remains opt-in. No CEFR/fluency/pronunciation score.

**New:** `backend/app/services/fluency_runtime_integration.py`, `backend/tests/test_fluency_runtime_integration.py`.

## Interface

```python
from app.services.fluency_runtime_integration import observe_fluency_timing

result = observe_fluency_timing(
    mp4_bytes, locale='fr-CA', consent=True,
    # only if independently checked against this exact recording:
    # verified_word_count=18, transcript_verified=True,
)
print(result.to_dict())
```

Results have `schema_version=fluency-observation-v1`, `status=EXPLORATORY_ONLY`, detector agreement, approximate detector runtime and nested temporal metrics. `MEASURED` in the nested timing means the computation had eligible VAD intervals; it **does not** imply VAD calibration or learner proficiency. Silence / no eligible speech returns `INSUFFICIENT_EVIDENCE`. Rates require verified word count. The current API receives a boolean attestation; it cannot independently prove transcript/recording binding. Do not pass ordinary STT word counts as independently verified.

## Security and limitations

- Consent must be obtained **for the specific recording** by an authenticated caller. This module checks a boolean but cannot verify identity, ownership, audit or authorization.
- The adapter may create a short-lived temporary audio file during FFmpeg MP4 fallback (Step 4.2b.1). No audio is deliberately persisted in the observation; abrupt process termination can leave temp files. Govern temporary-directory lifecycle separately.
- VAD timestamps, pause lengths, speech ratio, and tentative word rates are **observations**. No claims about hesitations, phonemes, pronunciation, accent, intelligibility, or fluency level.
- No API, migration, session/turn link, persistence, asynchronous process, or frontend change is included.
- No external provider, runtime model download, or paid call in tests.

## Tests (run from backend)

```powershell
python -m pytest -q tests/test_fluency_runtime_integration.py
python -m pytest -q
alembic current
```

The preceding complete suite contained 472 tests. This increment adds 29 parameterized tests (expected suite **501** if no other changes) and preserves Alembic `c5202601 (head)`.

## Acceptance & follow-up

The current tests use injected VAD responses; they check evidence gating and temporal integration, not real-model accuracy. After tests, run an optional local real-audio smoke test with a consented sample and the installed Silero model. Further calibration, user/session identity linking and reliable transcript verification are separate milestones, not silently assumed complete.
