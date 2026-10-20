import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationPanel } from "../components/ConversationPanel";
import { VoiceRecorder } from "../components/VoiceRecorder";
import { conversationsApi } from "../api/conversations";
import { createBrowserSpeechEngine } from "../services/browserSpeech";
import type { SpeechListener, SpeechSnapshot } from "../services/browserSpeech";

vi.mock("../api/conversations", () => ({ conversationsApi: { list: vi.fn(), submit: vi.fn() } }));
vi.mock("../services/browserSpeech", () => ({ createBrowserSpeechEngine: vi.fn() }));
const ids = { userId: "u", profileId: "p", sessionId: "s", speechLocale: "fr-CA" };
const dimension = { status: "correct", explanation: "OK", suggestion: null };
const feedback = { overall_assessment: "OK", grammar: dimension, vocabulary: dimension, clarity: dimension, naturalness: dimension,
  register: dimension, improved_version: "Bonjour", explanations: [], strengths: [], next_recommendation: "Continue" };
const turns = [{ turn_id: "old", turn_index: 1, learner_text: "Salut", coach_response: "Bonjour", feedback }];
let snapshot: SpeechSnapshot;
let listeners: Set<SpeechListener>;
const speak = vi.fn();
const stop = vi.fn();
const dispose = vi.fn();
const voices = [{ voiceURI: "fr-ca-1", name: "Canadian", lang: "fr-CA" }, { voiceURI: "en-ca-1", name: "English", lang: "en-CA" }] as SpeechSynthesisVoice[];
function emit(next: Partial<SpeechSnapshot>) {
  // This mock can be called synchronously from a React effect (autoplay).
  // Wrapping it in act() would nest a React work flush and crash with
  // "Should not already be working." UI interactions are already wrapped
  // by Testing Library; use act() at external event call sites if needed.
  snapshot = { ...snapshot, ...next };
  listeners.forEach(listener => listener({ ...snapshot }));
}
function setupEngine() {
  snapshot = { status: "idle", turnId: null, requestedLocale: null, selectedLocale: null, voiceURI: null, voiceMatch: null, error: null };
  listeners = new Set();
  speak.mockImplementation(({ turnId, locale }) => {
    emit({ status: "speaking", turnId, requestedLocale: locale, selectedLocale: locale, voiceURI: "fr-ca-1", voiceMatch: "exact" });
    return { ok: true, voiceMatch: "exact", selectedLocale: locale, voiceURI: "fr-ca-1" };
  });
  stop.mockImplementation(() => emit({ status: "idle", turnId: null }));
  vi.mocked(createBrowserSpeechEngine).mockImplementation(() => ({
    available: true, getSnapshot: () => ({ ...snapshot }), getVoices: () => voices,
    speak, stop, pause: vi.fn(), resume: vi.fn(), dispose,
    subscribe: listener => { listeners.add(listener); return () => { listeners.delete(listener); }; },
  }));
}
beforeEach(() => {
  vi.resetAllMocks(); window.localStorage.clear(); setupEngine();
  vi.mocked(conversationsApi.list).mockResolvedValue({ items: turns, limit: 50, offset: 0 } as never);
});

describe("VOX-001 preferences and autoplay integration", () => {
  it("does not autoplay historical messages or initial mount", async () => {
    window.localStorage.setItem("language-coach.voice-output.v1", JSON.stringify({ autoplay: true, rate: 1, voiceByLocale: {} }));
    render(<ConversationPanel {...ids} />);
    await within(screen.getByRole("list", { name: "Conversation history" })).findByText("Salut");
    expect(speak).not.toHaveBeenCalled();
  });
  it("autoplay opt-in speaks new coach response once, not when history reloads", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationsApi.submit).mockResolvedValue({ turn_id: "new", coach_response: "Bienvenue", feedback, turn_index: 2 } as never);
    const view = render(<ConversationPanel {...ids} />);
    await within(screen.getByRole("list", { name: "Conversation history" })).findByText("Salut");
    await user.click(screen.getByRole("checkbox", { name: /Automatically play new coach responses/ }));
    await user.type(screen.getByLabelText("Your message"), "Hello");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    expect(speak).toHaveBeenCalledWith({ turnId: "new", text: "Bienvenue", locale: "fr-CA", rate: 1 });
    view.rerender(<ConversationPanel {...ids} />);
    expect(speak).toHaveBeenCalledTimes(1);
  });
  it("keeps autoplay off unless explicitly enabled", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationsApi.submit).mockResolvedValue({ turn_id: "new", coach_response: "Bienvenue", feedback, turn_index: 2 } as never);
    render(<ConversationPanel {...ids} />);
    await within(screen.getByRole("list", { name: "Conversation history" })).findByText("Salut");
    await user.type(screen.getByLabelText("Your message"), "Hello");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    await waitFor(() => expect(conversationsApi.submit).toHaveBeenCalledTimes(1));
    expect(speak).not.toHaveBeenCalled();
  });
  it("persists rate and independent voice selections for different locales", async () => {
    const user = userEvent.setup();
    const view = render(<ConversationPanel {...ids} />);
    await within(screen.getByRole("list", { name: "Conversation history" })).findByText("Salut");
    await user.selectOptions(screen.getByLabelText("Playback speed"), "1.25");
    await user.selectOptions(screen.getByLabelText("Voice for fr-CA"), "fr-ca-1");
    await user.click(within(screen.getByLabelText("Audio controls for coach turn old")).getByRole("button", { name: "Listen" }));
    expect(speak).toHaveBeenCalledWith({ turnId: "old", text: "Bonjour", locale: "fr-CA", rate: 1.25, preferredVoiceURI: "fr-ca-1" });
    view.rerender(<ConversationPanel {...ids} speechLocale="en-CA" />);
    await user.selectOptions(screen.getByLabelText("Voice for en-CA"), "en-ca-1");
    expect(JSON.parse(window.localStorage.getItem("language-coach.voice-output.v1")!).voiceByLocale).toEqual({ "fr-CA": "fr-ca-1", "en-CA": "en-ca-1" });
  });
  it("registers a stop callback to cancel speech synchronously", async () => {
    const register = vi.fn();
    const view = render(<ConversationPanel {...ids} onRegisterSpeechStop={register} />);
    await within(screen.getByRole("list", { name: "Conversation history" })).findByText("Salut");
    const stopCallback = register.mock.calls.find(call => typeof call[0] === "function")?.[0];
    expect(stopCallback).toBeTypeOf("function");
    act(() => stopCallback());
    expect(stop).toHaveBeenCalled();
    view.unmount();
    expect(register).toHaveBeenCalledWith(null);
  });
});
