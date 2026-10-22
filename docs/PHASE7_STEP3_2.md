# Phase 7 — Step 3.2: Local Pronunciation Engine Feasibility

## Scope and decision

This increment is an **offline, privacy-preserving research probe** for paired learner/reference audio, **not** a pronunciation engine. It extends the Step 3.1 evidence-gated design without changing the existing provider factory, endpoint, database, UI, or Step 2 module.

**Engineering decision: No calibrated phoneme-level assessment engine is currently available in the local MVP.** Keep `LocalEvidenceGateProvider` as the production default. The probe is explicitly separate and never returns a pronunciation score. No external provider is enabled or approved.

## Included

- `backend/app/services/pronunciation_feasibility.py`: decodes two consented recordings with the Step 2 FFmpeg decoder; extracts duration, RMS dBFS, zero-crossing rate and energy-active fraction using 20 ms frames; reports signed reference deltas and processing latency.
- `backend/app/services/pronunciation_lab_cli.py`: optional **manual** CLI for running paired audio samples offline; no file storage or uploads.
- `backend/tests/test_pronunciation_feasibility.py`: 15 deterministic tests without real model calls, network access, FFmpeg runtime dependence or stored audio.

## Local execution

Run inside `backend/`. Make FFmpeg available in the same environment as Python.

```powershell
python -m pytest -q tests/test_pronunciation_feasibility.py
python -m pytest -q
alembic current
python -m app.services.pronunciation_lab_cli --help
python -m app.services.pronunciation_lab_cli --locale fr-CA --reference .\reference.wav --learner .\learner.wav --consent
```

The last command requires locally available recordings for which processing is authorized. For browser recordings, FFmpeg can decode WebM/Opus where the installed build supports it. CLI prints **statistics only**, not a transcript or raw signal. Redirect output only if you deliberately want to retain metadata. Audio stays in memory while processing; Python makes no explicit permanent copies. Operating-system or third-party decoder internals are outside this guarantee.

**Important:** reference examples should represent an appropriate locale, task and legitimate pronunciation variant. Different microphones, amplitude, rhythm, pitch, vocal tract, sex, gender, age, noise and recording quality are confounds. Even identical words can yield substantially different features. The file never needs to be added to the repository.

## Quality interpretation

- Duration difference: signed number of milliseconds, not an articulation error.
- RMS difference: gain/intensity difference, not accurate pronunciation.
- Zero-crossing rate difference: coarse signal-content difference, not a vowel or consonant classification.
- Activity ratio difference: threshold-dependent energy activity, not validated speech activity or linguistic pause.
- Execution time: local latency observation, not a benchmark until repeated under controlled hardware/configuration.

`outcome = EXPLORATORY_ONLY` deliberately cannot be mapped to `ASSESSED` or to `AssessmentDimension.score`.

## What would qualify as a real Step 3 MVP?

Collect consented human-annotated clips, including at least `fr-CA` and `en-CA`, with representative legitimate regional variants. Evaluate candidate phoneme or pronunciation models separately against human labels, measure error and uncertainty by locale/accent, and explicitly reject models with systematic unfairness. **No synthetic waveform or transcription accuracy test demonstrates pronunciation scoring accuracy.**

Candidate next experiments:

1. **Montreal Forced Aligner:** local phonetic alignment to *given* reference text; alignment success/timing is not correctness or accent grading. Its model card also warns against goodness-of-pronunciation use.
2. **WhisperX:** local word timestamp alignment for `fr`/`en`, model downloads/hardware constraints; not a phoneme-accuracy evaluator.
3. **Dedicated speech pronunciation assessment provider:** evaluate only with explicit approval for provider disclosure, cost and recording transmission.
4. **Human-labelled minimal pairs:** used to determine whether any candidate score distinguishes meaningful errors without punishing valid Québec variants.

## Data and security boundaries

- Consent in this lab is supplied by the operator; there is **no user-authenticated production authorization**. This is not a production endpoint.
- Never commit recordings or reference audio to the repository. Check permission to use reference clips; `--consent` is a manual attestation, not a consent-management service.
- The CLI refuses missing/oversize files; Step 2 FFmpeg subprocess has bounded duration and timeout and uses no shell.
- No persistent progress record, new migration, third-party SDK, GPU requirement or API cost.
- The full production engine remains gated `NOT_ASSESSED` until independent calibration and privacy review.

## Baseline and acceptance

Historical: 341 backend tests, 95 frontend tests, Alembic `c5202601 (head)`. This patch adds 15 backend tests, so expect **356 backend tests** if nothing else has changed. 15 tests passed in the isolated test harness with the previously delivered Step 1, 2 and 3.1 modules. Regression must be executed on the user's machine. There are no frontend changes.

Gate to Step 3.3: (a) green backend regression; (b) two locally consented recordings decoded successfully on Windows/Docker; (c) output labelled exploratory only; (d) approved, representative data evaluation plan; (e) human-label protocol drafted before any phoneme score.

## References (background, not locally validated)

- https://montreal-forced-aligner.readthedocs.io/en/stable/user_guide/index.html
- https://huggingface.co/MontrealCorpusTools/english_us_arpa
- https://github.com/m-bain/whisperX
