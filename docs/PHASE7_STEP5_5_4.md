# Phase 7 — Step 5.5.4: Bias & Failure Analysis

## Scope
An **offline descriptive** failure-analysis harness built on Step 5.5.2 versioned synthetic cases and Step 5.5.3 human-review contract. No model calls, network access, DB migration, or API changes.

## Files
- `backend/app/services/conversational_bias_analysis.py`
- `backend/tests/test_conversational_bias_analysis.py`
- `docs/PHASE7_STEP5_5_4.md`

## API
```python
from app.services.conversational_reference_bank import load_reference_case_bank
from app.services.conversational_bias_analysis import analyze_bias_and_failures

bank = load_reference_case_bank()
report = analyze_bias_and_failures(bank)  # no human references: comparison rates None
for group in report.slices:
    print(group.field, group.value, group.case_count, group.compared_cases,
          group.decision_agreement_rate, group.exclusions)
```

Pass tuples of versioned `HumanReview`, approved `AdjudicatedReference`, and `EvaluatorObservation` from Step 5.5.3 for meaningful human comparisons. All are verified against exact case text digests and approved review chains via the existing reliability analyzer.

## Report slices
- Locale: `fr-CA`, `en-CA`, `en-US`, `en-GB`.
- Context: professional/conversational.
- Scenario: executive update, stakeholder discussion, technical explanation, general.
- Input origin: `TYPED`, `USER_EDITED`, `STT_UNEDITED`, `VOICE_TEXT_UNKNOWN` where present.
- Challenge tags (overlap; counts across tags must not be summed).
- Length band: fewer than 4, 4–24, 25+ whitespace-delimited tokens.

Metrics include case coverage, observed model abstention, human-comparison agreement (only adjudicated cases), inappropriate ASSESS vs approved human ABSTAIN, excessive ABSTAIN vs human ASSESS, and explicit UNSUPPORTED flags. An `UNSUPPORTED` quality marker on a model observation is not itself proof of linguistic incorrectness without independent assessment.

## Safety and interpretation
The 16 synthetic texts are **not representative samples**. There are currently no real human-reference labels; numeric cross-group disparity, group fairness, statistical significance, discrimination, CEFR accuracy, and deployment readiness **cannot** be inferred. A zero comparable denominator yields `None`, not 0 or 100%. The model provenance `VOICE_TEXT_UNKNOWN` allows **text-only** analysis and never implies pronunciation quality or STT fidelity. No demographic characteristics are inferred or stored.

## Human review next steps
1. Collect two independent reviewers with FR-CA/EN regional expertise, blind to AI outputs where feasible.
2. Record rubric version and text SHA-256. Adjudicate disagreements explicitly, never silently synthesize labels.
3. Balance samples by locale, scenario, context, provenance and length; use real consented data only after privacy review.
4. Freeze evaluator version and test repeated outputs under controlled conditions. Report denominators, coverage gaps, disagreement examples (redacted), uncertainty, and action items.
5. Proceed to Step 5.5.5 closure only once evaluation evidence is reviewed. Production route remains NO_GO pending separate security readiness work.

## Validation
Within `backend`:
```powershell
python -m pytest -q tests/test_conversational_bias_analysis.py tests/test_conversational_reliability.py tests/test_conversational_reference_bank.py tests/test_conversational_calibration.py
python -m pytest -q
alembic current
```
Expected targeted: 55 passed (13 new + 42 prior). Alembic head remains `c5202603`. Full suite count depends on installed prior increments.
