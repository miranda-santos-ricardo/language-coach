# Phase 7 — Step 4.1: Evidence-Gated Temporal Metrics

## Scope
Additive pure-Python measurement module, no dependency changes, database migrations, routes, provider calls or raw-audio storage.
The module consumes validated **speech-specific** intervals supplied by a trusted detector outside this module. It *does not implement a VAD*. It prevents the Step 2 RMS acoustic intervals from being mislabeled as speech.

## Evidence contract
- `evidence_method=validated_speech_vad` may produce timing measurements when the caller supplies ordered, valid segments. This is a caller assertion about detector type; it does not prove detector calibration.
- `energy_activity` and `unavailable` yield `INSUFFICIENT_EVIDENCE`, with null timing measurements and no score.
- Pauses are **internal** (between speech segments) and filtered by `minimum_pause_ms`; leading and trailing quiet periods excluded.
- Speaking rate uses verified word count divided by the interval between *first speech start and last speech end*. Articulation rate divides verified word count by speech-only duration.
- STT output alone cannot guarantee word-count correctness. Until verified, do not output WPM.
- No CEFR, fluency grade, hesitation, pronunciation, intelligibility, accent or prosody score.

## Tests
From `backend/`:
```
python -m pytest -q tests/test_fluency_temporal.py
python -m pytest -q
alembic current
```
Frontend unchanged, but optional regression `npm test && npm run build`.
Baseline prior to change: 398 backend tests, migration head `c5202601`.

## Next increment — Step 4.2
Evaluate a speech-specific VAD behind an adapter (e.g. local Silero VAD). Before choosing implementation, verify Python 3.14 and deployment compatibility, model licenses and local inference resources. Establish speech/noise fixtures with timing annotations and compare RMS baseline versus VAD using precision/recall and interval timing tolerances. Keep audio solely in memory, with explicit processing consent. Do not wire API or persistence before repository inspection.
