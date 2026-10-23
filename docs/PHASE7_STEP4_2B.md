# Phase 7 — Step 4.2b: Real Silero Runtime & Audio Benchmark

## Scope
Offline, opt-in *real* Silero execution with the Step 4.2 `compare_speech_vad` adapter and a benchmark report. This package does **not** modify production endpoints, database or UI. No pronunciation or proficiency scoring. Automated tests use fakes; **real-model acceptance requires a separate manual run**.

## Prerequisites (Windows PowerShell, backend environment)

```powershell
python -m pip install "silero-vad==6.2.3"
python -c "import torch, silero_vad; print(torch.__version__)"
ffmpeg -version
```

Install dependencies only in the local research environment after reviewing the proposed changes; pin versions in a dedicated optional requirements file if accepted. `silero-vad` bundles model weights; this command does not use `torch.hub`, and model inference uses CPU. Package installation itself may access the internet to download dependencies. If package resolution fails on your platform, capture the error rather than changing the main production requirements. First import/model load may be slower than steady-state inference. Confirm Windows Python 3.14 wheel availability in your own environment.

Use a **consented 5–30 second** recording and no secret / production audio:

```powershell
python -m app.services.vad_runtime_benchmark_cli --audio .\samples\fr_ca_01.wav --locale fr-CA --consent > vad_report.json
```

The CLI prints intervals and metadata only, not audio. To compare against human annotation, create `annotation.json`:

```json
{"duration_ms": 3000, "speech_intervals": [{"start_ms":500,"end_ms":1300},{"start_ms":1700,"end_ms":2600}]}
```

Use a duration matching the **decoded** audio in milliseconds (small resampling/rounding differences may need adjustment). The intervals must be ordered, non-overlapping and within that duration:

```powershell
python -m app.services.vad_runtime_benchmark_cli --audio .\samples\fr_ca_01.wav --locale fr-CA --annotations .\annotation.json --consent > vad_report_annotated.json
```

Results include time-weighted IoU, precision, recall against human references where provided, and wall time / real-time factor. No thresholds establish accuracy before an independently annotated representative validation set is prepared. Run three times to separate cold and warm model load. Inspect how quiet speech and background noise affect results. All `EXPLORATORY_ONLY` outcomes require human review before use for coaching.

## Automated validation

```powershell
python -m pytest -q tests/test_vad_runtime_benchmark.py
python -m pytest -q
alembic current
```

Expected regression baseline **445 plus tests added here**; no new migrations. Run `npm test` and `npm run build` if a complete release check is desired; this increment does not modify frontend code.

## Limits

- `Silero` classifies probable speech and is not a pronunciation model.
- `RMS` comparisons are reference-free exploratory indicators, not validated accuracy.
- Human timestamps are not automatically ground truth; use independent annotations and adjudication.
- No files are automatically deleted: recordings and generated reports are under user control. Store these securely and delete according to the consent/retention plan.
- Model weights are loaded on each standalone invocation; process-cached warm latency requires separate measurement.
- No audio is transmitted intentionally by analysis code, but installing dependencies may access package repositories.
