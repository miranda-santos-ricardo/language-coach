/** Browser-only speech output. No HTTP, persistence, autoplay, or React dependency. */
export type SpeechStatus = "unavailable" | "idle" | "speaking" | "paused" | "error";
export type SpeechRate = 0.75 | 1 | 1.25;
export type VoiceMatch = "exact" | "language-fallback";

export interface CoachSpeechRequest {
  turnId: string;
  text: string;
  locale: string;
  rate?: SpeechRate;
  preferredVoiceURI?: string;
}

export interface SpeechSnapshot {
  status: SpeechStatus;
  turnId: string | null;
  requestedLocale: string | null;
  selectedLocale: string | null;
  voiceURI: string | null;
  voiceMatch: VoiceMatch | null;
  error: string | null;
}

export type SpeechListener = (snapshot: SpeechSnapshot) => void;
export type SpeechResult =
  | { ok: true; voiceMatch: VoiceMatch; selectedLocale: string; voiceURI: string }
  | { ok: false; reason: "disposed" | "unsupported" | "invalid-input" | "voice-unavailable" | "synthesis-error" };

export interface SpeechEngine {
  readonly available: boolean;
  getSnapshot(): SpeechSnapshot;
  getVoices(): SpeechSynthesisVoice[];
  speak(request: CoachSpeechRequest): SpeechResult;
  pause(): void;
  resume(): void;
  stop(): void;
  subscribe(listener: SpeechListener): () => void;
  dispose(): void;
}

/** Inject browser globals only at construction time, never at module import time. */
export interface BrowserSpeechDependencies {
  synthesis?: SpeechSynthesis | null;
  createUtterance?: (text: string) => SpeechSynthesisUtterance;
}

function validLocale(value: string): string | null {
  try {
    return Intl.getCanonicalLocales(value.trim())[0] ?? null;
  } catch {
    return null;
  }
}

function selectVoice(
  voices: SpeechSynthesisVoice[],
  locale: string,
  preferredVoiceURI?: string,
): { voice: SpeechSynthesisVoice; match: VoiceMatch } | null {
  const language = locale.split("-")[0].toLowerCase();
  const compatible = voices
    .map((voice) => ({ voice, tag: validLocale(voice.lang) }))
    .filter((item): item is { voice: SpeechSynthesisVoice; tag: string } => !!item.tag)
    .filter((item) => item.tag.split("-")[0].toLowerCase() === language);
  const exact = compatible.filter((item) => item.tag.toLowerCase() === locale.toLowerCase());
  const candidates = exact.length ? exact : compatible;
  if (!candidates.length) return null;
  // A preferred voice never overrides a locale-exact voice with a regional fallback.
  const picked = candidates.find(({ voice }) => voice.voiceURI === preferredVoiceURI) ??
    candidates.find(({ voice }) => voice.default) ?? candidates[0];
  return { voice: picked.voice, match: exact.length ? "exact" : "language-fallback" };
}

export function createBrowserSpeechEngine(dependencies: BrowserSpeechDependencies = {}): SpeechEngine {
  const browser = typeof window === "undefined" ? null : window;
  const synthesis = dependencies.synthesis !== undefined
    ? dependencies.synthesis
    : (browser?.speechSynthesis ?? null);
  const createUtterance = dependencies.createUtterance ?? (
    typeof SpeechSynthesisUtterance !== "undefined"
      ? (text: string) => new SpeechSynthesisUtterance(text)
      : null
  );
  const supported = !!synthesis && !!createUtterance;
  let disposed = false;
  let generation = 0;
  let current: SpeechSynthesisUtterance | null = null;
  let snapshot: SpeechSnapshot = {
    status: supported ? "idle" : "unavailable",
    turnId: null, requestedLocale: null, selectedLocale: null,
    voiceURI: null, voiceMatch: null, error: null,
  };
  const listeners = new Set<SpeechListener>();
  let voiceCache: SpeechSynthesisVoice[] = [];

  const publish = (next: SpeechSnapshot) => {
    snapshot = next;
    if (!disposed) listeners.forEach((listener) => listener({ ...snapshot }));
  };
  const getVoices = (): SpeechSynthesisVoice[] => {
    if (!supported || disposed) return [];
    try {
      voiceCache = synthesis!.getVoices();
    } catch {
      voiceCache = [];
    }
    return [...voiceCache];
  };
  const onVoicesChanged = () => {
    getVoices();
    if (!disposed) publish({ ...snapshot });
  };
  if (supported) {
    getVoices();
    synthesis!.addEventListener?.("voiceschanged", onVoicesChanged);
  }

  const clearCurrent = () => {
    if (current) {
      current.onstart = null;
      current.onend = null;
      current.onerror = null;
      current.onpause = null;
      current.onresume = null;
      current = null;
    }
  };
  const stop = () => {
    if (disposed) return;
    generation++;
    clearCurrent();
    try { synthesis?.cancel(); } catch { /* best effort */ }
    publish({ status: supported ? "idle" : "unavailable", turnId: null,
      requestedLocale: null, selectedLocale: null, voiceURI: null,
      voiceMatch: null, error: null });
  };
  const speak = (request: CoachSpeechRequest): SpeechResult => {
    if (disposed) return { ok: false, reason: "disposed" };
    if (!supported) return { ok: false, reason: "unsupported" };
    const locale = typeof request.locale === "string" ? validLocale(request.locale) : null;
    if (!request.turnId?.trim() || !request.text?.trim() || !locale ||
        (request.rate !== undefined && !([0.75, 1, 1.25] as number[]).includes(request.rate))) {
      return { ok: false, reason: "invalid-input" };
    }
    stop();
    const picked = selectVoice(getVoices(), locale, request.preferredVoiceURI);
    if (!picked) {
      publish({ ...snapshot, status: "unavailable", requestedLocale: locale,
        error: `No compatible voice for ${locale}` });
      return { ok: false, reason: "voice-unavailable" };
    }
    const token = ++generation;
    try {
      const utterance = createUtterance!(request.text);
      current = utterance;
      utterance.lang = picked.voice.lang;
      utterance.voice = picked.voice;
      utterance.rate = request.rate ?? 1;
      const alive = () => !disposed && token === generation && current === utterance;
      utterance.onstart = () => {
        if (alive()) publish({ ...snapshot, status: "speaking" });
      };
      utterance.onpause = () => {
        if (alive()) publish({ ...snapshot, status: "paused" });
      };
      utterance.onresume = () => {
        if (alive()) publish({ ...snapshot, status: "speaking" });
      };
      utterance.onend = () => {
        if (alive()) stop();
      };
      utterance.onerror = (event) => {
        if (!alive()) return;
        generation++;
        clearCurrent();
        publish({ ...snapshot, status: "error", error: event.error || "Speech synthesis failed" });
      };
      publish({ status: "speaking", turnId: request.turnId, requestedLocale: locale,
        selectedLocale: picked.voice.lang, voiceURI: picked.voice.voiceURI,
        voiceMatch: picked.match, error: null });
      synthesis!.speak(utterance);
      return { ok: true, voiceMatch: picked.match, selectedLocale: picked.voice.lang, voiceURI: picked.voice.voiceURI };
    } catch {
      generation++;
      clearCurrent();
      publish({ ...snapshot, status: "error", error: "Speech synthesis failed" });
      return { ok: false, reason: "synthesis-error" };
    }
  };
  const pause = () => {
    if (disposed || snapshot.status !== "speaking") return;
    try { synthesis?.pause(); publish({ ...snapshot, status: "paused" }); }
    catch { publish({ ...snapshot, status: "error", error: "Unable to pause speech" }); }
  };
  const resume = () => {
    if (disposed || snapshot.status !== "paused") return;
    try { synthesis?.resume(); publish({ ...snapshot, status: "speaking" }); }
    catch { publish({ ...snapshot, status: "error", error: "Unable to resume speech" }); }
  };
  const dispose = () => {
    if (disposed) return;
    stop();
    disposed = true;
    synthesis?.removeEventListener?.("voiceschanged", onVoicesChanged);
    listeners.clear();
  };
  return {
    get available() { return supported && !disposed; },
    getSnapshot: () => ({ ...snapshot }), getVoices, speak, pause, resume, stop,
    subscribe(listener) {
      if (disposed) return () => {};
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    }, dispose,
  };
}
