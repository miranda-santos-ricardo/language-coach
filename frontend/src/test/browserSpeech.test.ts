import { describe, expect, it, vi } from "vitest";
import { createBrowserSpeechEngine } from "../services/browserSpeech";

const voice = (lang: string, id = lang, isDefault = false) => ({
  lang, voiceURI: id, name: id, default: isDefault, localService: true,
}) as SpeechSynthesisVoice;

function fakeBrowser(initialVoices: SpeechSynthesisVoice[] = [voice("fr-CA")]) {
  let voices = initialVoices;
  const callbacks = new Map<string, Set<EventListener>>();
  const spoken: SpeechSynthesisUtterance[] = [];
  const synthesis = {
    getVoices: vi.fn(() => voices),
    speak: vi.fn((utterance: SpeechSynthesisUtterance) => { spoken.push(utterance); }),
    pause: vi.fn(), resume: vi.fn(), cancel: vi.fn(),
    addEventListener: vi.fn((name: string, fn: EventListener) => {
      if (!callbacks.has(name)) callbacks.set(name, new Set());
      callbacks.get(name)!.add(fn);
    }),
    removeEventListener: vi.fn((name: string, fn: EventListener) => callbacks.get(name)?.delete(fn)),
  };
  const createUtterance = vi.fn((text: string) => ({ text, lang: "", voice: null, rate: 1,
    onstart: null, onend: null, onerror: null, onpause: null, onresume: null,
  }) as unknown as SpeechSynthesisUtterance);
  const engine = createBrowserSpeechEngine({ synthesis: synthesis as unknown as SpeechSynthesis, createUtterance });
  const dispatch = (name: string) => callbacks.get(name)?.forEach((cb) => cb(new Event(name)));
  const setVoices = (newVoices: SpeechSynthesisVoice[]) => { voices = newVoices; dispatch("voiceschanged"); };
  return { engine, synthesis, spoken, createUtterance, setVoices, dispatch, callbacks };
}
const request = { turnId: "turn-1", text: "Bonjour, comment allez-vous ?", locale: "fr-CA" };

describe("BrowserSpeechService — VOX-001", () => {
  it("does not access browser APIs at import; unsupported environments fail safely", () => {
    const engine = createBrowserSpeechEngine({ synthesis: null, createUtterance: () => { throw Error("not called"); } });
    expect(engine.available).toBe(false);
    expect(engine.getSnapshot().status).toBe("unavailable");
    expect(engine.speak(request)).toEqual({ ok: false, reason: "unsupported" });
    expect(engine.getVoices()).toEqual([]);
    engine.pause(); engine.resume(); engine.stop(); engine.dispose();
  });

  it("selects fr-CA over fr-FR regardless of voice order", () => {
    const f = fakeBrowser([voice("fr-FR"), voice("fr-CA")]);
    expect(f.engine.speak(request)).toMatchObject({ ok: true, voiceMatch: "exact", selectedLocale: "fr-CA" });
    expect(f.spoken[0].lang).toBe("fr-CA");
    f.engine.dispose();
  });

  it("reports explicit regional fallback, not a fictional Quebec voice", () => {
    const f = fakeBrowser([voice("fr-FR")]);
    expect(f.engine.speak(request)).toMatchObject({ ok: true, voiceMatch: "language-fallback", selectedLocale: "fr-FR" });
    expect(f.engine.getSnapshot().voiceMatch).toBe("language-fallback");
    f.engine.dispose();
  });

  it("prefers en-CA over en-US and en-GB", () => {
    const f = fakeBrowser([voice("en-GB"), voice("en-US"), voice("en-CA")]);
    expect(f.engine.speak({ ...request, locale: "en-CA" })).toMatchObject({ ok: true, selectedLocale: "en-CA", voiceMatch: "exact" });
    f.engine.dispose();
  });

  it("does not use a voice from the wrong language", () => {
    const f = fakeBrowser([voice("en-US")]);
    expect(f.engine.speak(request)).toEqual({ ok: false, reason: "voice-unavailable" });
    expect(f.engine.getSnapshot().status).toBe("unavailable");
    expect(f.synthesis.speak).not.toHaveBeenCalled();
    f.engine.dispose();
  });

  it("refreshes voices after voiceschanged and removes listener on dispose", () => {
    const f = fakeBrowser([]);
    expect(f.engine.speak(request)).toEqual({ ok: false, reason: "voice-unavailable" });
    const listener = vi.fn();
    f.engine.subscribe(listener);
    f.setVoices([voice("fr-CA")]);
    expect(listener).toHaveBeenCalled();
    expect(f.engine.getVoices()).toHaveLength(1);
    expect(f.engine.speak(request).ok).toBe(true);
    f.engine.dispose();
    expect(f.synthesis.removeEventListener).toHaveBeenCalledWith("voiceschanged", expect.any(Function));
  });

  it("speaks only supplied text at an allowed rate", () => {
    const f = fakeBrowser();
    expect(f.engine.speak({ ...request, rate: 0.75 }).ok).toBe(true);
    expect(f.createUtterance).toHaveBeenCalledWith(request.text);
    expect(f.spoken[0].rate).toBe(0.75);
    expect(f.engine.getSnapshot().status).toBe("speaking");
    f.engine.dispose();
  });

  it("pause resume stop are idempotent", () => {
    const f = fakeBrowser();
    f.engine.pause(); f.engine.resume();
    expect(f.synthesis.pause).not.toHaveBeenCalled();
    f.engine.speak(request);
    f.engine.pause(); f.engine.pause();
    expect(f.synthesis.pause).toHaveBeenCalledTimes(1);
    expect(f.engine.getSnapshot().status).toBe("paused");
    f.engine.resume(); f.engine.resume();
    expect(f.synthesis.resume).toHaveBeenCalledTimes(1);
    f.engine.stop(); f.engine.stop();
    expect(f.engine.getSnapshot().status).toBe("idle");
    f.engine.dispose();
  });

  it("cancels prior speech and discards delayed events", () => {
    const f = fakeBrowser();
    f.engine.speak(request);
    const first = f.spoken[0];
    const oldEnd = first.onend;
    f.engine.speak({ ...request, turnId: "turn-2", text: "Salut !" });
    expect(f.synthesis.cancel).toHaveBeenCalled();
    oldEnd?.call(first, {} as SpeechSynthesisEvent);
    expect(f.engine.getSnapshot()).toMatchObject({ status: "speaking", turnId: "turn-2" });
    f.engine.dispose();
  });

  it("refuses empty text, missing turn ID, invalid locale or unsupported rates", () => {
    const f = fakeBrowser();
    for (const bad of [
      { ...request, text: "  " }, { ...request, turnId: "" },
      { ...request, locale: "not_a_locale" }, { ...request, rate: 2 as 1 },
    ]) expect(f.engine.speak(bad)).toEqual({ ok: false, reason: "invalid-input" });
    expect(f.synthesis.speak).not.toHaveBeenCalled();
    f.engine.dispose();
  });

  it("turns synthesis failure into explicit error without leaking content", () => {
    const f = fakeBrowser();
    f.engine.speak(request);
    const utterance = f.spoken[0];
    utterance.onerror?.call(utterance, { error: "network" } as SpeechSynthesisErrorEvent);
    expect(f.engine.getSnapshot()).toMatchObject({ status: "error", error: "network" });
    f.engine.dispose();
  });

  it("handles synchronous speak exceptions", () => {
    const f = fakeBrowser();
    f.synthesis.speak.mockImplementationOnce(() => { throw Error("driver failure"); });
    expect(f.engine.speak(request)).toEqual({ ok: false, reason: "synthesis-error" });
    expect(f.engine.getSnapshot().status).toBe("error");
    f.engine.dispose();
  });

  it("dispose cancels and prevents later callbacks or calls", () => {
    const f = fakeBrowser();
    f.engine.speak(request);
    const oldStart = f.spoken[0].onstart;
    const listener = vi.fn();
    f.engine.subscribe(listener);
    f.engine.dispose();
    listener.mockClear();
    oldStart?.call(f.spoken[0], {} as SpeechSynthesisEvent);
    expect(listener).not.toHaveBeenCalled();
    expect(f.engine.speak(request)).toEqual({ ok: false, reason: "disposed" });
    expect(f.engine.available).toBe(false);
  });

  it("does not make any fetch calls", () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => { throw Error("No HTTP allowed"); });
    try {
      const f = fakeBrowser();
      f.engine.speak(request);
      f.engine.stop(); f.engine.dispose();
      expect(fetchMock).not.toHaveBeenCalled();
    } finally { fetchMock.mockRestore(); }
  });
});
