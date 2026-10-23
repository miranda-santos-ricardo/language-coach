# Phase 7 — Step 5.2: Professional Communication Rubrics

## Scope

Incremental, **non-scoring** rubric catalog and a validation adapter compatible with `conversational_evidence.py` (Step 5.1). No database changes, APIs, external calls, or modifications to prior files.

Five dimensions, preserving the Step 5.1 order: `relevance`, `coherence`, `professional_register`, `clarity`, `persuasiveness`. Four locales: `fr-CA`, `en-CA`, `en-US`, `en-GB`. Contexts: `professional` and `conversational`. Scenarios: `executive_update`, `stakeholder_discussion`, `technical_explanation`, `general`.

Rubrics are **English-language reviewer guidelines** usable for evaluating writing in all supported locales; they are not yet localized learner feedback. Professional register is contextual, not inherently superior. Regional varieties, accent and fluency are not graded.

## Reviewer protocol

1. Acquire the authenticated user's authorized conversation-turn evidence through the application layer; do not trust `authorized_turn=True` from a client.
2. Select rubric using declared locale, context and scenario type. Preserve text provenance (`STT_UNEDITED`, `USER_EDITED`, `TYPED`).
3. Ensure reviewer knows the *actual* audience, communicative task, and goals. A short snippet cannot always sustain conclusions across all five dimensions.
4. For each dimension: abstain (`INSUFFICIENT_EVIDENCE` or `NOT_ASSESSED`) OR submit an observation with direct verbatim excerpt and reviewer provenance. Persuasiveness is applicable only to a scenario explicitly framed as persuasion, argumentation or recommendation.
5. Submit through `validate_rubric_review(...)`; it enforces stable dimension order, declared rubric and reviewer provenance, and exact quote presence via the Step 5.1 gate.
6. Never treat the gate as independent semantic evaluation: the quoted fragment can be in the text while the asserted judgment still is wrong. Model-review outputs remain labeled `MODEL_JUDGMENT`, with no calibrated scoring.

## Integration boundary

```python
from app.services.professional_communication_rubrics import get_communication_rubric
rubric = get_communication_rubric(locale='fr-CA', context='professional', scenario_type='executive_update')
print(rubric.to_dict())
```

`validate_rubric_review` accepts `ConversationalEvidence` and `RubricReviewSubmission`, returning the existing `ConversationalAssessmentDraft`. This is a reviewer-provenance / contract check, not an LLM call or guarantee of fairness or accuracy.

## Validation

```powershell
cd backend
python -m pytest -q tests/test_professional_communication_rubrics.py
python -m pytest -q
alembic current
```

No external API, paid call, or migration. No new database tables. Files in this ZIP are additions only. Run with all prior Phase 7 packages in the working tree.

## Limitations and next increment

No actual text evaluation, no scores or CEFR, no benchmark calibration, no learner UI. The persuasion gate uses conservative scenario keywords and may abstain for paraphrased persuasive tasks; refine via an explicit trusted task-intent field if required. Next: Step 5.3 — Controlled Conversational Evaluator with schema validation and offline adversarial fixtures.
