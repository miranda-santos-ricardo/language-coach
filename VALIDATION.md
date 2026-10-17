# Phase 5 — Step 11, Increment 1: End-to-End Integration & Regression Validation

## Scope and guarantees

- Six backend HTTP integration tests traverse the actual FastAPI routers, SQLAlchemy models/repositories, orchestration, and structured feedback, using an in-memory SQLite test database and **fake STT + fake LLM**. No paid inference or real microphone is used.
- Existing frontend tests cover VoiceRecorder, explicit transcript transfer, conversation UI, resume, ordering/pagination, and stale-response isolation; run the whole suite.
- This is **component-level/in-process E2E**, not a full physical-browser + live-PostgreSQL + OpenAI E2E. The manual checklist below covers those gaps.
- No application code, migrations, or frontend code changed in this increment.

## Install

Extract the ZIP at the root of `language-coach`. The new Python test lives at `backend/tests/test_phase5_e2e_flow.py`. Do not copy `STEP11_VALIDATION.md` under `backend`.

## Automated, offline (zero OpenAI calls)

```powershell
cd backend
python -m pytest -q tests/test_phase5_e2e_flow.py
python -m pytest -q
alembic current
cd ../frontend
npm test
npm run build
```

Expected baseline plus new tests: backend 302 tests (296 + 6), frontend 55 tests, Alembic `c5202601 (head)`, TypeScript/Vite build successful. The total may vary if local files have changed.

## Manual E2E scenarios (mark evidence and actual results)

| ID | Scenario | Procedure | Expected result | Result / evidence |
|---|---|---|---|---|
| M01 | French voice path | Start active fr-CA profile; record voice; transcribe; **do not** transfer yet | Transcript visible, no coach request and no new conversation turn | |
| M02 | Explicit transfer and edit | Click *Use transcript in coach*; edit text | Draft changes to voice mode, no POST until *Send to Coach* | |
| M03 | AI reply and feedback | Click *Send to Coach* (see paid-call note below) | Coach response and structured feedback rendered and retrievable after refresh | |
| M04 | English text and multi-turn | Switch to en-CA profile; submit 2 text messages | Target-language reply, ordered turn indexes, correct history context | |
| M05 | Resume | Leave active session; reselect profile; *Find active sessions*, resume | Same PracticeSession and saved turns recovered | |
| M06 | Error recovery | Stop backend temporarily or simulate an HTTP failure before submission | Draft retained; retries avoid duplicate turn; no secret leakage | |
| M07 | Separation | Switch profile/session while history fetch pending | No old-session messages appear in new session | |
| M08 | Session lifecycle | Finish session; revisit history; try to submit another turn | Existing history readable; new POST rejected | |
| M09 | Invalid input/audio | Empty text, invalid audio, oversized audio | Controlled 4xx, no completed turn from invalid input | |
| M10 | Concurrent POST | With test PostgreSQL environment and two independent connections, send simultaneous turns to the same session | One active operation at a time; second receives documented conflict; no duplicate indexes | |
| M11 | Regional/professional quality | Evaluate fr-CA B2 + en-CA professional scenario manually | Record *subjective* usefulness, false-positive corrections, register and CEFR; do not infer quality from fixture pass | |
| M12 | Local mobile mic | Use HTTPS secure context via local tunnel or trusted local certificate (do not expose unauthenticated service publicly) | Microphone permission works on phone; transcript reaches editor only after explicit action | |

### Paid-call boundary

M03/M04/M11 with actual OpenAI inference or real STT **may consume credits**. Do **not** run those against the paid provider without explicit authorization. You can defer these and record `NOT RUN — paid calls not authorized`, or use configured local/fake providers. No paid calls are made by the automated tests included here. If you authorize live tests later, record the exact number of calls, model, date and approximate cost.

### Database and security limitations

- Automated suite uses SQLite; PostgreSQL migration, `pg_try_advisory_xact_lock` multi-connection contention, server restart and TLS are **not proven** by this test.
- User IDs in URLs are not authentication; application must not be exposed publicly before real authenticated identity enforcement.
- For mobile microphone on a LAN, browsers commonly require a secure context (HTTPS or localhost).
- Do not downgrade live databases as part of manual validation.

## Definition-of-Done evidence for Step 11 Increment 1

Record backend and frontend test counts, Vite build, migration head, each manual scenario result and failures. Step 11 closes only after the later closure report separates verified behavior from deferred production/security/linguistic checks.
