# Phase 7 — Step 4.5: Fluency Validation & Step 4 Closure

## Objective and scope

An opt-in, local validation path for the previously implemented Step 4 components:

`audio bytes -> FFmpeg (including seekable MP4 fallback) -> Silero speech VAD -> TemporalMetrics -> FluencyObservation -> FluencyFeedback -> JSON report`.

New files:
- `backend/app/services/fluency_validation.py`
- `backend/app/services/fluency_validation_cli.py`
- `backend/tests/test_fluency_validation.py`

This package **adds no HTTP endpoint, migration, frontend change, LLM call, CEFR or fluency score**. It does not provide calibrated ground truth.

## Local automated acceptance

From `backend`:

```powershell
python -m pytest -q tests/test_fluency_validation.py
python -m pytest -q
alembic current
```

Expected: **29** new tests; **556** backend tests total if the previously verified **527** remain unchanged; Alembic `c5202601 (head)`.

The isolated tests use injected deterministic detectors. Their success does not establish model accuracy, runtime availability or real-audio quality.

## Real offline smoke test (requires locally installed Silero weights, FFmpeg)

```powershell
python -m app.services.fluency_validation_cli `
  --audio .\samples\fr_ca_01.mp4 `
  --locale fr-CA `
  --context professional `
  --consent > fluency_validation_report.json

Get-Content .\fluency_validation_report.json
```

Check:
- `status`: `EXPLORATORY_ONLY` for detected likely speech or `INSUFFICIENT_EVIDENCE` for no speech.
- `observation.detector`: `silero-vad-local`.
- `observation.timing.speech_intervals`, `speech_duration_ms`, `internal_pause_intervals`, `speech_ratio`.
- `feedback.status`: `OBSERVATIONAL_ONLY` or `INSUFFICIENT_EVIDENCE`.
- `feedback.items`: contextual observations and optional practice, with an explicit calibration limitation.
- `speaking_rate_wpm`, `articulation_rate_wpm`: **null**; there is no independently verified lexical count.

The CLI outputs a JSON report without the recording or transcript. Redirection saves *metadata* locally, not audio. The decoder may briefly create private temporary files for seek-dependent MP4s; hard process termination may prevent cleanup.

## Manual validation matrix

Use only consented local recordings. Inspect the audio by ear (informal QA is **not** a calibrated reference).

| Case | Expected safe behavior |
|---|---|
| Android MP4/AAC with speech | Decoder succeeds; plausible speech segments; observational feedback only |
| Local WAV/PCM with speech | Same contract; no format-specific score |
| Silence | `INSUFFICIENT_EVIDENCE`, no practice implying a fluency deficit |
| Background noise | May produce false positives; do not claim accuracy or fluency |
| Naturally long rhetorical pause | A measured timing observation is not labeled a deficit |
| Corrupt/unreadable audio | `FAILED` with error type only, nonzero exit |
| Missing `--consent` | Rejects without reading the file or running inference |
| Unsupported locale | Argparse rejects before processing |
| Audio over 10 MiB or decoded duration >60s | Controlled rejection |
| Optional VAD not installed | Controlled failure, without model auto-download |

For higher confidence, evaluate independent, time-aligned speech/noise annotations from multiple speakers and recording conditions. Tune thresholds only on a held-out set; track precision/recall, boundary tolerance and latency. **Silero–RMS IoU is not a calibration metric.**

## Closure decision

**Closed — implementation and deterministic test scope:** contracts, MP4 seek fallback, opt-in local VAD, temporal calculations, safe feedback templates, CLI, regression of Step 4.5.

**Still open — production readiness:** independent annotation-based VAD calibration; reproducibility across devices and noise; authenticated ownership and recording-bound consent; operational management of temporary audio files; HTTP/session binding, durable idempotency and privacy review; UI and accessibility; frontend regression and E2E.

This step should be marked *experimental technical closure*, not calibrated fluency assessment or complete Phase 7 feature release. Do not represent timing as user proficiency, hesitations, pronunciation quality, accent, or CEFR.
