# Phase 7 — Step 5.1: Conversational Intelligence Evidence Contracts

## Scope

Pure local contracts and admission gates for text-based communication assessment. This is an initial increment of Step 5, **not** an LLM evaluator, grading system, API endpoint, migration, or frontend integration.

- Supported locales: fr-CA, en-CA, en-US, en-GB.
- Contexts: professional and conversational.
- Dimensions, in stable order: relevance, coherence, professional_register, clarity, persuasiveness.
- Text sources: STT_UNEDITED (requires original STT provenance), USER_EDITED, TYPED.
- Authenticated ownership is **caller-attested**; the FastAPI boundary must validate actual user/session/turn ownership before setting `authorized_turn=True`.
- Short input abstains. Otherwise, the baseline is `AWAITING_EVALUATOR` and all dimensions are NOT_ASSESSED.
- Reviewed observations require declared human/model provenance, evaluator version, exactly one entry per dimension, and supporting snippets that occur verbatim in the submitted text.
- Presence of a snippet does **not** establish correctness of any judgment. Calibration, adjudication, instruction-injection resistance, and rubric quality need independent validation.
- No scores, CEFR inference, pronunciation judgments, STT fidelity claims, or audio data.

## Data policy

The function consumes text transiently. It does not write files, send requests, or store text. Do not log supplied transcripts, quotes, scenario, or identifiers. The caller must check user ownership and authorization, and decide whether retaining submitted text is appropriate.

## Relation to previous phases

Step 1 defines the overarching SpeechAssessment and evidence graph. This step is a **separate preliminary contract**, not a replacement for existing schemas. Step 4 acoustic findings must remain distinct from text-derived communication observations. User edits to STT must not be labeled as exactly spoken words.

## Installation and verification

Unzip into the repository root; no existing files are replaced.

```powershell
cd backend
python -m pytest -q tests/test_conversational_evidence.py
python -m pytest -q
alembic current
```

Expected full backend count: prior 556 + new tests collected. Count must be verified in the user's environment. No migration required.

## Next increments

5.2 — rubric specification with positive/negative examples and model-judgment calibration dataset; 5.3 — controlled evaluator adapter with strict JSON contracts and prompt-injection-resistant handling; 5.4 — authentic-turn integration with idempotency and ownership; 5.5 — acceptance and multilingual fairness tests. No numeric proficiency score until calibrated against independently reviewed cases.
