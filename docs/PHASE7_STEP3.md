# Phase 7 — Step 3: Pronunciation evidence gate (first increment)

## Decision
The current Step 2 energy detector does not measure pronunciation. An audio-derived phonetic pronunciation score cannot be responsibly delivered with the installed components. This first Step 3 increment implements the provider contract and an explicit offline abstention path (`NOT_ASSESSED`). It is **not** a pronunciation-scoring MVP. A second increment is necessary before Step 3 can be considered functionally complete.

- New `PronunciationRequest` validates explicit processing consent, supported locales, reference text and audio size/type.
- `PronunciationAssessmentProvider` protocol isolates future calibrated pronunciation engines.
- `LocalEvidenceGateProvider` returns honest `NOT_ASSESSED` output; converts it to the Phase 7 Step 1 schema.
- No network, database, endpoint, mutation, retention, dependency, migration, or cost.
- Never interpret energy activity, STT confidence or textual fluency as pronunciation accuracy.
- `processing_consent` is trusted only after verification by the application/service layer; a user-supplied flag must never serve as proof by itself.
- Buffer-content validation and safe audio decode are responsibilities of a future orchestration layer, before selecting a provider.

## Technical landscape
Azure AI Speech Pronunciation Assessment supports fr-CA, en-CA, en-US and en-GB, but granular output varies by locale; prosody assessment is documented as en-US only. An Azure adapter must remain disabled by default and requires authorization for external audio transfer/cost. A local G2P / force-alignment result would not constitute pronunciation accuracy without human-calibrated acoustic testing.

## Testing
From backend after extracting ZIP at repository root:

```bash
python -m pytest -q tests/test_pronunciation_assessment.py
python -m pytest -q
alembic current
```

Frontend regression (unchanged):

```bash
npm test
npm run build
```

## Next experiment to complete Step 3
1. Select a narrow *scripted* reference phrase set for fr-CA/en-CA/en-US/en-GB and consented recordings.
2. Obtain human annotated reference judgments (including legitimate accent variants).
3. Benchmark either a genuinely phonetic offline engine or an explicitly authorized cloud trial against these labels.
4. Introduce a typed `ASSESSED` output with audio evidence IDs, provider/rubric versions, confidence limitations, missing-data behavior, and rejection/fallback tests.
5. Only integrate into conversation flow after passing quality and privacy gates.

No claim of real pronunciation assessment is made by this increment.
