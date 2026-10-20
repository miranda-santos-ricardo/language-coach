import { beforeEach, describe, expect, it, vi } from "vitest";
import { canonicalSpeechLocale, compatibleSpeechVoices, loadSpeechPreferences, saveSpeechPreferences, SPEECH_PREFERENCES_KEY } from "../services/speechPreferences";

beforeEach(() => window.localStorage.clear());
const voice = (lang: string, id: string) => ({ lang, voiceURI: id, name: id }) as SpeechSynthesisVoice;

describe("VOX-001 browser voice preferences", () => {
  it("defaults to autoplay disabled, normal rate, automatic voice", () => {
    expect(loadSpeechPreferences()).toEqual({ autoplay: false, rate: 1, voiceByLocale: {} });
  });
  it("persists preferences including independent FR-CA and EN-CA voice choices", () => {
    saveSpeechPreferences({ autoplay: true, rate: 0.75, voiceByLocale: { "fr-CA": "quebec-1", "en-CA": "english-1" } });
    expect(loadSpeechPreferences()).toEqual({ autoplay: true, rate: 0.75, voiceByLocale: { "fr-CA": "quebec-1", "en-CA": "english-1" } });
  });
  it("rejects invalid stored JSON and invalid rates without throwing", () => {
    window.localStorage.setItem(SPEECH_PREFERENCES_KEY, "{invalid");
    expect(loadSpeechPreferences().autoplay).toBe(false);
    window.localStorage.setItem(SPEECH_PREFERENCES_KEY, JSON.stringify({ autoplay: "yes", rate: 9, voiceByLocale: { "fr-CA": 9 } }));
    expect(loadSpeechPreferences()).toEqual({ autoplay: false, rate: 1, voiceByLocale: {} });
  });
  it("does not throw when browser storage is disabled", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(() => saveSpeechPreferences({ autoplay: true, rate: 1.25, voiceByLocale: {} })).not.toThrow();
    spy.mockRestore();
  });
  it("prefers exact regional voices and only shows same-language fallbacks if needed", () => {
    const voices = [voice("fr-FR", "paris"), voice("en-US", "us"), voice("fr-CA", "quebec")];
    expect(compatibleSpeechVoices(voices, "fr-CA").map(v => v.voiceURI)).toEqual(["quebec"]);
    expect(compatibleSpeechVoices(voices.slice(0, 2), "fr-CA").map(v => v.voiceURI)).toEqual(["paris"]);
    expect(canonicalSpeechLocale("EN-ca")).toBe("en-CA");
  });
});
