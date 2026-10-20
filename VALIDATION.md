# Phase 6 Step 3 — VOX-001 Preferences & Autoplay

## Installation
Extract this ZIP at the root of `language-coach/`, overwriting the included frontend paths only. Keep your Step 1 and Step 2 changes in place.

## Files
- `frontend/src/services/speechPreferences.ts` (new): resilient localStorage preferences with default autoplay OFF and locale-specific voice choices.
- `frontend/src/components/ConversationPanel.tsx` (updated): voice settings UI and autoplay only after a newly submitted turn; stops on session change and unmount.
- `frontend/src/components/PracticeSessionStarted.tsx` (updated): synchronous TTS stop callback on Leave and confirmed Complete; connects recorder.
- `frontend/src/components/VoiceRecorder.tsx` (updated): optional callback before `startRecording` (STT workflow unchanged).
- `frontend/src/test/CoachAudioPlayback.test.tsx` (updated): playback speed is now a shared session preference; retains previous Step 2 act() fix.
- `frontend/src/test/speechPreferences.test.ts` (new): persistence and voice selection tests.
- `frontend/src/test/CoachVoicePreferences.test.tsx` (new): autoplay, per-language voice selection, and callback integration.
- `frontend/src/test/VoiceRecordingStopsSpeech.test.tsx` (new): microphone priority.

## Run
```bash
cd frontend
npm test -- src/test/speechPreferences.test.ts src/test/CoachVoicePreferences.test.tsx src/test/VoiceRecordingStopsSpeech.test.tsx src/test/CoachAudioPlayback.test.tsx
npm test
npm run build
```

Expected: 11 new tests (5 + 5 + 1). The last confirmed baseline was 76 tests; Step 2 added 7, so approximately **94 tests** total if your working tree matches the completed Step 2 and no other tests were added. Verify the actual count reported by Vitest.

## Manual checks
1. Start in FR-CA. Autoplay checkbox is OFF; load history and assert there is no spoken audio.
2. Select a compatible French voice, set 0.75x speed, click Listen. Refresh; preferences persist.
3. Enable autoplay. Submit a NEW text or transcribed voice message; only the new `coach_response` is spoken. Refresh/Resume should NOT speak history.
4. Click Start recording while the coach is speaking; the audio must stop before microphone capture starts. Repeat with an old historical response.
5. Speak, switch sessions, Leave & Resume Later, then Complete Session; speech stops in each case.
6. Switch to English, choose an English voice. Switch back to French and confirm its selection is preserved.
7. If no exact regional voice exists, select a displayed same-language fallback and confirm the UI indicates the selected voice locale during playback.
8. Confirm text chat and STT transcript-to-coach still work with autoplay OFF. If a browser has no Web Speech API, voice settings and playback cannot produce sound but typing must still work.

## Constraints / known limitations
- Autoplay is OFF by default; no audio generated during mounting or history loading.
- `localStorage` is per browser/device, not per application account. No database migration or server API changes.
- Voice availability varies by browser, OS and installed voices. Web Speech API does not guarantee offline processing.
- No OpenAI TTS calls are made; actual conversational LLM/STT API calls remain under existing application configuration.
- Do not consider this increment validated until Vitest, Vite build and the manual browser checks succeed on your environment.
