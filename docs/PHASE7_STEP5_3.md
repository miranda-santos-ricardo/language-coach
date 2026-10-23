# Phase 7 — Step 5.3 Controlled Conversational Evaluator

## Scope

This is a **controlled experimental adapter**, not an HTTP endpoint or production LLM integration. It wraps the Step 5.1 evidence contract and Step 5.2 professional communication rubrics. Model calls are supplied by the authenticated application as an injected function, enabling deterministic offline tests without paid API calls.

### Added files

- `backend/app/services/controlled_conversational_evaluator.py`
- `backend/tests/test_controlled_conversational_evaluator.py`
- `docs/PHASE7_STEP5_3.md`

No migrations or dependency changes.

## Flow

1. The caller authenticates the user and verifies session/turn ownership. It must construct `ConversationalEvidence` from trusted application state, not accept `authorized_turn=True` from the frontend.
2. `build_evidence_gate` abstains for unusably short texts, **without calling** a model.
3. The evaluator selects a versioned rubric and creates `EvaluationRequest(system_instructions, user_payload)`, where submitted content is JSON-encoded as untrusted data.
4. The caller-provided `model_call(request)` executes once, returning a JSON string or dictionary. The application must configure model/provider, data handling, token limits, privacy notices, consent, costs, retries and timeouts.
5. The response decoder strictly rejects extra top-level keys, wrong shapes, unknown labels/statuses, altered ordering, unwanted scoring fields or invalid provenance.
6. Step 5.2 rubric validation requires exact quotes from the original submitted text and refuses persuasive assessments without a declared persuasive intent.
7. Accepted output is `ConversationalAssessmentDraft` with `MODEL_JUDGMENT` provenance, never `HUMAN_REVIEWED` or CEFR/fluency/pronunciation scores.

## Provider adapter example (offline only)

```python
from app.services.controlled_conversational_evaluator import evaluate_conversation

# evidence is a trusted, authenticated ConversationalEvidence from your application.
# The fake function returns the full strict JSON envelope specified by the module.
result = evaluate_conversation(
    evidence,
    scenario_type='executive_update',
    evaluator_version='mock-v1',
    model_call=fake_model_call,
)
```

## Validation

From `backend`:

```powershell
python -m pytest -q tests/test_controlled_conversational_evaluator.py
python -m pytest -q
alembic current
```

Baseline Step 5.2: 611 backend tests. This increment adds 26 tests; **expected 637 tests** if the baseline is unchanged. `alembic current` should remain `c5202601 (head)`.

## Limitations and next integration steps

- System/user prompt separation and JSON encapsulation **reduce**, but do not eliminate, prompt injection risks. Model judgments and quotations need independent evaluation and adversarial testing.
- Quotation validation checks literal presence, **not** interpretive validity. The service cannot verify factual correctness or calibration.
- Caller-attested authorization is insufficient for production; authoritative user/session/turn ownership and idempotency must be integrated at the API/database boundary.
- No direct calls to the existing LLM implementation were made because its current source/interfaces were not available for inspection; preserve its established timeout, retry, and structured-output contracts during Step 5.4.
- Underlying provider exceptions are chained for local debugging but the publicly displayed `EvaluatorFailure` string is sanitized; production logging policy must avoid raw prompt/response disclosures.
- Scores, CEFR labels, human-review claims, audio features, and pronunciation judgments are intentionally unsupported.
