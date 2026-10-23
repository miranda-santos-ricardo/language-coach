# Phase 7 — Step 4.2: Local Speech VAD & Temporal Calibration (increment 1)

## Scope
Offline comparison of **Silero speech VAD** with the existing RMS acoustic-activity detector. No production endpoint, database change, frontend change, cloud provider, model download at inference time, learning score, or new mandatory dependencies.

## Dependencies / install (optional experimental environment)
The default app/test environment needs no new package. For a *real* Silero run, install a compatible PyTorch + `silero-vad` version **in a separate experimental environment**, after checking the Windows Python 3.14 wheel and Docker image. CPU is sufficient for feasibility benchmarks; GPU is not assumed. Follow the upstream packaging instructions at https://github.com/snakers4/silero-vad. The implementation uses the installed package with a lazy import and **never `torch.hub`**. Avoid on-demand model downloads; pre-stage the bundled model artifacts in a controlled image and assess licensing/security before deployment.

The existing FFmpeg decoder provides 16kHz mono PCM. `get_speech_timestamps` expects a 1-D waveform and outputs sample offsets; this adapter converts them to milliseconds and validates range and ordering. `compare_speech_vad` also runs the energy-activity probe. Intersection-over-union (IoU) describes agreement of **two algorithms only**, *not accuracy*. VAD segments are passed to the Step 4.1 temporal calculator; word-rate requires separately verified word counts and is deliberately absent in this increment.

## How to test
From `backend/`:

```powershell
python -m pytest -q tests/test_local_speech_vad.py
python -m pytest -q
alembic current
```

## Real-audio calibration protocol (next increment)
Use consented, local-only clips under 60 seconds and 10 MiB: quiet, noise, music, silence, French Canadian and several English accents. Obtain human-annotated speech start/end times; compute boundary MAE, speech/none false positives, recall, precision, and benchmark CPU latency. Include short utterances, rhetorical pauses and interruptions. Record hardware, locale, environment, detector and threshold versions. Do **not** interpret locale labels as model language understanding, or RMS/VAD agreement as ground truth. Never send audio to external providers without explicit permission.

## Caveats
- Tests use an injected deterministic fake rather than invoking real Silero weights, so they validate adapters and error handling, **not VAD detection accuracy**.
- No statements about phonemes, pronunciation, comprehension, fluency level or progress are supported.
- Timestamp padding/default thresholds may merge short pauses; calibration must precede pedagogical presentation.
- Production security, isolation, consent persistence and performance remain out of scope.
