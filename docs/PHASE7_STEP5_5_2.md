# Phase 7 — Step 5.5.2: Multilingual Reference Case Bank

## Goal
Versioned, **synthetic** and fully offline FR-CA / English scenarios compatible with the Step 5.5.1 `CalibrationCase` harness, spanning executive updates, stakeholder discussions, technical explanations and everyday conversations. These are *challenge examples*, not clinical/linguistic ground truth and not validated learner performances.

## Delivered

- `backend/app/evaluation/conversation_cases_v1.json`: 16 fictional, versioned cases. Includes FR-CA, en-CA, en-US and en-GB, professional/conversational context, ambiguous or short text, regional expressions, and `VOICE_TEXT_UNKNOWN`.
- `backend/app/services/conversational_reference_bank.py`: strict UTF-8 loader, bank validation, metadata filters, descriptive coverage and `CalibrationCase` adapter.
- `backend/tests/test_conversational_reference_bank.py`: no-network deterministic tests.

All cases have `human_reference: null` and `reference_status: SYNTHETIC_UNREVIEWED`. `challenge_tags` and `review_focus` denote what to investigate, not what a reviewer concluded. Short examples should elicit abstention when evidence is insufficient, but the bank does **not** contain unverified mandatory labels. A value of `STT_UNEDITED` in fictional data tests contract handling; it is not evidence of a real audio recording.

## Running

From `backend/`:

```powershell
python -m pytest -q tests/test_conversational_reference_bank.py tests/test_conversational_calibration.py
python -m pytest -q
alembic current
```

Expected Alembic head: `c5202603`; no migrations. The existing backend test count increases by the number of newly collected tests in this file, subject to the current checkout.

## Quality / review process for 5.5.3

1. Recruit at least two independent reviewers fluent in the **specific locale**. Seek banking/insurance professional communication experience where relevant.
2. Remove identifying data from new examples; obtain consent and appropriate retention policy before using learner-derived text.
3. Collect per-dimension binary *assess vs abstain* reference annotations separately from evidence support, correctness, severity, and actionability judgments. Preserve independent annotations and disagreements.
4. Adjudicate references, document rubric and reviewer agreement; publish reviewed references separately with a distinct signed-off version.
5. Test the model blind on a held-out set, stratifying by locale, register, scenario, length and provenance. Report missing references instead of imputing agreement or CEFR.
6. Never equate substring occurrence with semantic evidence correctness. Never infer pronunciation, fluency or original-utterance fidelity from committed text.

## Limitations

No model calls, no real human annotation, no CEFR scoring, no model quality estimates, no endpoint activation. Production status remains **NO_GO**, independent of any case-bank completeness.
