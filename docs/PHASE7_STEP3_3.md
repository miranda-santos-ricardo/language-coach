# Phase 7 — Step 3.3: Human Reference Evaluation & Calibration (Increment 1)

## Scope
Offline, metadata-only audit of a small, consented human-annotated reference corpus.
This is **not** a pronunciation engine, diagnostic score, phoneme detector, validation of regional fairness, or training dataset. No microphone or API integration.

## Files
- `backend/app/services/pronunciation_calibration.py`: strict manifest validation, coverage and inter-annotator exact agreement.
- `backend/app/services/pronunciation_calibration_cli.py`: offline CLI; reads metadata-only JSON, outputs aggregate report to stdout.
- `backend/tests/test_pronunciation_calibration.py`: deterministic tests, no network/paid provider.

## Manifest contract (`calibration-v1`)
```
{
  "schema_version": "calibration-v1",
  "recordings": [{"id":"r01","locale":"fr-CA","scenario":"executive_update","method_version":"coarse-audio-reference-probe-v0.1","capture_condition":"quiet_room","reference_id":"ref01"}],
  "annotations": [
    {"recording_id":"r01","annotator_id":"judge-a","intelligibility":"intelligible","pronunciation_observation":"no_specific_issue_observed","regional_variant_valid":true},
    {"recording_id":"r01","annotator_id":"judge-b","intelligibility":"partly_intelligible","pronunciation_observation":"specific_issue_observed","regional_variant_valid":null}
  ]
}
```
Only opaque IDs. No learner names, audio paths, transcript, recording bytes, audio hashes, detailed error descriptions, or other sensitive information in the manifest.

Human labels are provisional observations, **not objective phonetic truth**. Intelligibility categories: `intelligible`, `partly_intelligible`, `not_intelligible`, `cannot_judge`. Pronunciation observation categories: `no_specific_issue_observed`, `specific_issue_observed`, `cannot_judge`. The `regional_variant_valid` flag reflects one annotator's judgment, not automatic correctness.

## Run
From backend directory:
```
python -m pytest -q tests/test_pronunciation_calibration.py
python -m pytest -q
alembic current
python -m app.services.pronunciation_calibration_cli --manifest .\my_private_manifest.json
```
Keep private manifests, consent receipts and recordings outside the Git working tree, and do not check them into source control. The CLI does not ingest audio or make network calls.

## Report interpretation
- `dual_annotated_recordings`: how many clips have >=2 independent raters.
- `exact_agreement_fraction`: matching human **intelligibility category** labels over all eligible rater pairs (excluding `cannot_judge` pairs); it is **not** accuracy, Cohen's kappa, or model agreement.
- `coverage_status`: `READY_FOR_REVIEW` requires at least 3 dual-annotated recordings and 3 eligible rater pairs per locale (lab readiness only). This is a minimal engineering gate, not statistical sufficiency or clinical/pedagogical validation.
- `regional_variant_valid_flags`: number of positive human flags; **not** evidence of regional fairness. Explicit disagreement analysis and representative sample design are still needed.

## Human audio experiment still required
Collect consented clips for controlled target phrases and freer speaking scenarios in four locales, with at least two qualified independent evaluators. Separate speech intelligibility from regional norms, recording conditions and CEFR. Hold out recordings for validation. Record separate approved technical metadata for reference quality and capture device only after privacy review. In later calibration, compare candidate phonetic providers to human annotations; do not interpret Step 3.2 coarse acoustic deltas as phoneme correctness.

## Deferred / acceptance
No schema migration, API, frontend, or production feedback changes. Step 3.3 is not complete until the human corpus, rater protocol, consent/retention procedure, inter-rater reliability (including beyond-chance statistic where appropriate), regional fairness review and technical benchmark are completed. This ZIP is only the first calibration infrastructure increment.
