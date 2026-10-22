# Phase 7 — Step 2: Local Speech Analysis Feasibility Prototype

## Scope

**Research prototype, not production speech VAD or pronunciation assessment.** Adds two new files and this guide. No modification to the Step 1 contracts, existing APIs, DB, recording flow, or frontend. No model downloads, paid API calls or recording persistence.

## Why this approach

`ffmpeg` decodes container formats (including most browser WebM/Opus and MP4 recordings) into mono 16-kHz signed PCM **in memory**. A deterministic frame-RMS threshold measures *acoustic activity*, not speech. This lets us independently test audio decoding, durations, temporal intervals, failure handling, local latency and feasibility without falsely labeling generic acoustic energy as spoken fluency.

Silero VAD is an optional candidate for a later, separate experiment. It requires an installed package/model and benchmark on consented voices. WhisperX word alignment is also deferred: timestamps from forced alignment are not pronunciation quality scores.

## Files

- `backend/app/services/speech_analysis_prototype.py` — isolated probe.
- `backend/tests/test_speech_analysis_prototype.py` — synthetic PCM/WAV test cases only.
- `docs/PHASE7_STEP2.md` — operational instructions and validation.

## Setup (Windows and Docker)

Check `ffmpeg -version` from the shell **running pytest**. If testing in a backend Docker container, ffmpeg must also be installed in that container. This ZIP deliberately does not modify Dockerfiles or download binaries. Run from `backend`:

```bash
python -m pytest -q tests/test_speech_analysis_prototype.py
python -m pytest -q
alembic current
```

From `frontend`:

```bash
npm test
npm run build
```

The probe can be imported directly:

```python
from pathlib import Path
from app.services.speech_analysis_prototype import probe_audio_activity
result = probe_audio_activity(Path('consented-sample.webm').read_bytes())
print(result.to_dict())
```

Never commit real recordings to the repository. The example runs locally and does not save decoded audio. Original audio is passed as bytes and exists in process memory during analysis. Don't print audio contents or transcripts.

## Input contract / limits

- Encoded `bytes`, ≤ 10 MiB, <= 60s decoded audio, timeout 12s (configurable).
- Uses `ffmpeg` through `subprocess.run` with a fixed argv, `shell=False`, stdin/stdout pipes, no file paths.
- Resample to 16 kHz mono s16le, energy frames of 20 ms; default -35 dBFS threshold, minimum active 120 ms, bridge gaps <=100 ms.
- On malformed audio, unavailable ffmpeg, failed decoder or timeout, raises `AudioAnalysisError` (no underlying file content in message).
- Results indicate `ACTIVITY_DETECTED` or `NO_ACTIVITY_DETECTED`, and include method/version, active intervals, *internal* inactive intervals, durations, threshold and limitations.
- Not robust against music, ambient noise, overlapping voices, extreme gain, auto-gain, or codecs with leading encoder padding. Does not label pauses, fluency, speaking rate, pronunciation, prosody or intelligibility.

## Evaluation follow-up before Step 3

1. Benchmark local Windows vs Docker on short *consented* `fr-CA`, `en-CA`, `en-US` audio. Measure decoding latency and failures; do not log raw content.
2. Obtain independently annotated intervals of true speech on a small, privacy-safe sample set. Compare energy intervals vs ground truth (false positives on noise/music, false negatives on low-volume speech).
3. Test optional true speech VAD (e.g. Silero) in isolated experiment and measure CPU/RAM/latency and generalization to different accents and noise.
4. Decide if VAD reliability is sufficient for *pauses*; only then build Step 4 fluency metrics. Never interpret fixed energy alone as speech quality.
5. For actual pronunciation assessment, evaluate a provider using consented reference recordings and native/human-reviewed judgments in Step 3; missing capability should return NOT_ASSESSED.

## Acceptance criteria

- All 9 prototype unit tests pass (no `skip`); if skipped, ffmpeg is missing and Step 2 is not fully validated.
- Existing backend/frontend regression unchanged; Alembic stays `c5202601 (head)`.
- No real external calls, no migrations, no changed API behavior and no persisted raw audio.
- Record sample-format compatibility (actual browser webm/opus if available), latency, and false positive caveats.

## Changelog

Added deterministic, offline decoding/energy-interval probe; added generated-fixture tests and operational feasibility guide. No existing files changed.
