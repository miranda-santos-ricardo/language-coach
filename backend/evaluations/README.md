# Language Coach — Phase 5 evaluation dataset v1

All `reference_output` records are **synthetic, manually authored fixtures**. They are used to test JSON schema compatibility, declared expectations, and a few canary checks. Passing these checks does **not** establish linguistic correctness, regional appropriateness, conversational usefulness, or resistance to prompt injection.

`expected_statuses` contains human-authored expectations for selected dimensions; other dimensions can vary. The subsequent Step 10 increment should run a separately approved, budget-bounded set of real LLM samples and review them with human rubrics. No real inference occurs here.

Run `python -m pytest -q tests/test_evaluation_dataset.py`. The dataset is `evaluations/coach_cases_v1.json`. Evaluation input is never interpolated into a system prompt by this test suite.
