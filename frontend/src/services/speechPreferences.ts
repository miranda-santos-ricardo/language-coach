import type { SpeechRate } from "./browserSpeech";

export const SPEECH_PREFERENCES_KEY = "language-coach.voice-output.v1";

export interface SpeechPreferences {
  autoplay: boolean;
  rate: SpeechRate;
  /** Preference per canonical speech locale; stored as the browser voiceURI. */
  voiceByLocale: Record<string, string>;
}

export const DEFAULT_SPEECH_PREFERENCES: SpeechPreferences = {
  autoplay: false,
  rate: 1,
  voiceByLocale: {},
};

const rates: readonly number[] = [0.75, 1, 1.25];
export function canonicalSpeechLocale(locale: string): string {
  try { return Intl.getCanonicalLocales(locale)[0] ?? locale; }
  catch { return locale; }
}

/** localStorage may be absent/blocked in private browsing or tests. Never throw. */
export function loadSpeechPreferences(): SpeechPreferences {
  try {
    const raw = window.localStorage.getItem(SPEECH_PREFERENCES_KEY);
    if (!raw) return { ...DEFAULT_SPEECH_PREFERENCES, voiceByLocale: {} };
    const stored: unknown = JSON.parse(raw);
    if (typeof stored !== "object" || stored === null || Array.isArray(stored)) throw Error("Invalid preferences");
    const value = stored as Record<string, unknown>;
    const voices = value.voiceByLocale;
    const entries = typeof voices === "object" && voices !== null && !Array.isArray(voices)
      ? Object.entries(voices).filter(([key, uri]) => key.length <= 40 && typeof uri === "string" && uri.length <= 500)
      : [];
    return {
      autoplay: value.autoplay === true,
      rate: typeof value.rate === "number" && rates.includes(value.rate) ? value.rate as SpeechRate : 1,
      voiceByLocale: Object.fromEntries(entries),
    };
  } catch { return { ...DEFAULT_SPEECH_PREFERENCES, voiceByLocale: {} }; }
}

export function saveSpeechPreferences(preferences: SpeechPreferences): void {
  try { window.localStorage.setItem(SPEECH_PREFERENCES_KEY, JSON.stringify(preferences)); }
  catch { /* Storage is optional. Preferences still work until component unmount. */ }
}

export function compatibleSpeechVoices(voices: SpeechSynthesisVoice[], locale: string): SpeechSynthesisVoice[] {
  const requested = canonicalSpeechLocale(locale).toLowerCase();
  const lang = requested.split("-")[0];
  const compatible = voices.filter(v => canonicalSpeechLocale(v.lang).toLowerCase().split("-")[0] === lang);
  const exact = compatible.filter(v => canonicalSpeechLocale(v.lang).toLowerCase() === requested);
  // Keep fallback choices available, but prioritize exact regional voices.
  return exact.length > 0 ? exact : compatible;
}
