# Phase 6 — Step 1: Browser Speech Service (VOX-001)

## Scope
- Adds only `frontend/src/services/browserSpeech.ts` and `frontend/src/test/browserSpeech.test.ts`.
- No modification to React components, backend, database, API, dependencies or migrations.
- No autoplay, HTTP requests or paid voice services.
- Types: `CoachSpeechRequest`, `SpeechRate`, `SpeechSnapshot`, `SpeechResult`, `SpeechEngine`.
- Public factory: `createBrowserSpeechEngine(dependencies?)`.

## Apply
Unzip into the **repository root**, preserving `frontend/src/...` paths. Do not replace existing files.

## Run (from repository root)
```sh
cd frontend
npm test -- src/test/browserSpeech.test.ts
npm test
npm run build
```

Expected: 14 new unit tests and the previously reported 62 tests (approximately 76 total), assuming the existing baseline and tests have not changed. Verify exact count from Vitest; no backend test count changes.

## API usage for Step 2 (not wired yet)
```ts
import { createBrowserSpeechEngine } from "./services/browserSpeech";
const engine = createBrowserSpeechEngine();
const unsubscribe = engine.subscribe((snapshot) => {
  // snapshot.status: idle | speaking | paused | unavailable | error
  // snapshot.voiceMatch: exact | language-fallback | null
});
engine.speak({ turnId: "<actual-turn-id>", text: "Bonjour !", locale: "fr-CA", rate: 1 });
engine.pause();
engine.resume();
engine.stop();
unsubscribe();
engine.dispose();
```

### Decisions
- Voice selection: exact requested BCP-47 locale; otherwise same-language voice; do not silently select a different language. Regional fallback is surfaced in `SpeechResult.voiceMatch` and `SpeechSnapshot.voiceMatch`.
- `preferredVoiceURI` is honored only inside the best available locale tier.
- If no compatible voice is available, `speak` returns `voice-unavailable`; UI should allow retry after `voiceschanged`.
- Browser TTS may rely on cloud-backed voices from the browser/OS; this code performs no explicit network calls.
- Voice catalog refresh sends a snapshot notification to subscribers; Step 2 should query `getVoices()` again if needed.
- One engine per active session; call `stop` at session switch/recording start and `dispose` on unmount.
- User gesture may be needed to start speech on mobile.
- No integration with `ConversationPanel`, `PracticeSessionStarted` or `VoiceRecorder` yet; that belongs to Step 2.

## Validation performed in this workspace
- TypeScript strict compilation of the new service alone passed with `tsc --noEmit --strict --target ES2022 --module ESNext --lib ES2022,DOM`.
- Full `npm test` and `npm run build` remain to be validated in the user's installed frontend environment.
