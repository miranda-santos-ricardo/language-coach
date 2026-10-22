# Phase 7 — Step 3 Windows pytest corrective patch

## Root cause
The oversize-audio pytest parameter generated a node ID containing more than 10 MiB of zero characters. Pytest stores the node ID in PYTEST_CURRENT_TEST and Windows rejects an environment-variable value longer than 32767 characters. Errors occurred during pytest setup/teardown; audio validation assertions were not the cause.

## Fix
Use stable short IDs for the existing three parameter cases (empty, invalid_type, oversized). No change to inputs, assertions, or production code.

## Apply
Extract this ZIP at the repository root, replacing only backend/tests/test_pronunciation_assessment.py.

## Validate
From backend:
python -m pytest -q tests/test_pronunciation_assessment.py
python -m pytest -q
alembic current

From frontend:
npm test
npm run build

Expected targeted result: 13 passed (if dependencies and contract are unchanged).
