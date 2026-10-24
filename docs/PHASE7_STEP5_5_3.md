# Phase 7 — Step 5.5.3: Evaluator Reliability & Human Reference Agreement

## Scope
This increment adds a deterministic, offline reliability analysis service on top of the Phase 7 Step 5.5.1 calibration harness and the Step 5.5.2 synthetic 16-case reference bank. No models, providers, live endpoints, DB tables or migrations are modified.

## Delivered
- `backend/app/services/conversational_reliability.py` — immutable contracts for independent human annotations, signed-off adjudications and evaluator observations. It compares *assess vs abstain* decisions independently from manually reviewed evidence correctness and feedback quality; version/checksum and reviewer provenance gates; excludes missing human data instead of hallucinating labels. Provides dimension-level disagreement records and explicit comparison denominators.
- `backend/tests/test_conversational_reliability.py` — 13 deterministic tests with fabricated annotations used **only as testing fixtures**, not as research-quality human ground truth.

## Review protocol
1. Use cases from `conversation_cases_v1.json`, with unchanged case IDs and texts. Obtain real independent, locale-qualified reviewers with appropriate language/register expertise. Do not use learner content without consent and retention controls.
2. Give at least two distinct reviewers the identical rubric version and case text **without access to model output**. Record per-dimension `ASSESS`/`ABSTAIN`; if assess, independently evaluate evidence correctness and actionable feedback quality (`SUPPORTED`, `UNSUPPORTED`, `UNCERTAIN`, or `NOT_REVIEWED`). The `text_sha256` must be derived from exact case text.
3. Adjudicate reviewer differences explicitly; `AdjudicatedReference(approved=True)` must represent genuine sign-off, **not** an automatically inferred majority or generated reference. Store annotator sign-offs in a controlled repository outside the synthetic bank.
4. Separately obtain frozen evaluator observations of the same text and evaluator version. Evidence/feedback quality labels must come from actual human analysis of the evaluated output, not be inferred from quoted substring presence or by the model itself.
5. Run `analyze_reliability(bank, reviews, references, observations)`. Inspect `disagreements` and `exclusions`. Report comparison denominators by locale, scenario and context before drawing conclusions; this harness does not claim robust statistical power.
6. Keep a stratified held-out set and do not tune against the held-out set. Never infer audio fidelity, pronunciation, CEFR mastery, or production authorization from text-only results.

## Interpretation
`decision_agreement_rate`: assessed-vs-abstained agreement against **approved human adjudications**, not semantic correctness or CEFR accuracy.
`reviewer_agreement_rate`: pairwise assess-vs-abstain agreement between two independent reviewers (not kappa).
`evidence_agreement_rate` / `feedback_agreement_rate`: agreement of explicitly supplied human quality judgments on cases where both sides decided to assess, **not** a measure from unreviewed model output. `None` means no comparable data, not zero or 100%.

The 16 reference cases remain `SYNTHETIC_UNREVIEWED` with `human_reference: null`. No accuracy result or release confidence is established by this package. `release_ready` remains `False`; production `NO_GO` until PostgreSQL tests, real OIDC provider and operational controls are separately validated.

## Validation
From backend:
```powershell
python -m pytest -q tests/test_conversational_reliability.py tests/test_conversational_reference_bank.py tests/test_conversational_calibration.py
python -m pytest -q
alembic current
```
Expected newly added tests: **13**; combined local tests for Steps 5.5.1–5.5.3: **42**; Alembic unchanged at `c5202603 (head)`.

## Next
Step 5.5.4: Bias & Failure Analysis — stratified analysis for locale/register/provenance/length, disagreements and abstention. Human annotation and review still required to assert real-world reliability.
