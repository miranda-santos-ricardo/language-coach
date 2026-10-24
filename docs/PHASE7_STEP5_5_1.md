# Phase 7 — Step 5.5.1: Conversational Calibration Harness

## Scope

This is the **first increment** of Step 5.5. It provides an offline, deterministic harness for checking outputs against the Step 5.1/5.2 evidence contracts. No production endpoint, migration, LLM call, or frontend change.

## What the metrics mean

- `contract_valid`: shape, dimension coverage, declared provenance, exact quote presence and appropriate abstention. Quote containment does **not** demonstrate that a quote supports the inference.
- `abstention_rate`: share of dimensions that do not contain `MODEL_JUDGMENT` in valid drafts. This is descriptive, not a quality target.
- `human_agreement_rate`: when independently adjudicated human references exist, **agreement on assessed versus abstained only**. It does **not** measure semantic correctness, inter-rater reliability, CEFR validity, or quality of the feedback. When no reference exists it is `None`, never 100%.
- `release_ready` is always `False`: these tests alone cannot certify release.

## Calibration sequence (planned incremental work)

1. **5.5.1 (this package):** deterministic contracts, error taxonomy, reference-ready case model, conservative report.
2. **5.5.2:** write balanced, consent-safe FR-CA and EN case bank across locale, scenario, register, STT provenance, short texts, code-switching, ambiguity and persuasive/nonpersuasive tasks. Human labels must be produced *independently*, ideally by two reviewers with adjudication; synthetic examples cannot substitute for human gold labels.
3. **5.5.3:** connect deterministic offline model mocks and saved, deidentified response artifacts. Evaluate actual semantic agreement and citation usefulness only with well-defined human annotations; control evaluator version, prompt version, model version and case-bank version.
4. **5.5.4:** analyze slice-level disagreement, abstention, bias, reliability and failure modes; set thresholds **after** observing pilot baseline and human inter-rater disagreement. No invented numerical release thresholds.
5. **5.5.5:** signed-off closure report covering evidence and residual risks. Production activation remains NO_GO until real OIDC/JWKS, PostgreSQL concurrency tests, and operational controls are validated.

## Install & validate

Extract into repository root. In `backend` run:

```powershell
python -m pytest -q tests/test_conversational_calibration.py
python -m pytest -q
alembic current
```

Expected: 12 new tests; baseline previous suite plus 12, assuming preceding incremental packages installed. Expected Alembic head `c5202603 (head)`; no migration in this step.

## Security limitations

The calibration harness receives explicitly authorized, previously prepared drafts from an injected callable. It does **not** authenticate users or issue assessment requests. Do not use learner personal text in distributed calibration assets without consent and minimization. Voice provenance UNKNOWN supports only evaluation of submitted text, never pronunciation or transcript fidelity.
