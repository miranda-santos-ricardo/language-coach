# Phase 6 — Step 2: Coach Audio Playback

## Scope
- `frontend/src/components/ConversationPanel.tsx` — per-turn controls, shared speech engine, session lifecycle cancellation.
- `frontend/src/components/PracticeSessionStarted.tsx` — pass effective session locale.
- `frontend/src/test/CoachAudioPlayback.test.tsx` — seven integration tests with fake speech engine.

No backend/database/migration/OpenAI changes. Autoplay intentionally absent.

## Apply
Extract this overlay at the root of `language-coach`. Keep `frontend/src/services/browserSpeech.ts` from Step 1 (already validated).

## Validate
```bash
cd frontend
npm test -- src/test/CoachAudioPlayback.test.tsx
npm test
npm run build
```
Baseline: 76 prior passing tests. Expected 83 tests / 11 test files if all seven pass.

## Manual
1. Open an active FR-CA session with existing coach messages. Verify no automatic speech.
2. Select Listen for a response, Pause, Resume, Stop, Repeat; vary speed.
3. Switch to another turn: only the selected turn should play.
4. Leave & Resume Later; verify sound stops. Resume: old messages remain playable.
5. Complete a session; sound stops once the panel unmounts after successful completion.
6. Try an EN-CA profile; check voice choice and fallback messages.
7. Try a browser without compatible voices; check clear explanatory message.

Note: Browsers may load speech voices asynchronously. If a voice is unavailable initially, try again after they have loaded. Regional voice fidelity depends on OS/browser installation. No TTS provider API cost; the browser may still use platform-provided network speech services.
