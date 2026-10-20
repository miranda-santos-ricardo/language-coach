import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationPanel } from "../components/ConversationPanel";
import { conversationsApi } from "../api/conversations";
import { createBrowserSpeechEngine } from "../services/browserSpeech";
import type { SpeechListener, SpeechSnapshot } from "../services/browserSpeech";

vi.mock("../api/conversations", () => ({ conversationsApi: { list: vi.fn(), submit: vi.fn() } }));
vi.mock("../services/browserSpeech", () => ({ createBrowserSpeechEngine: vi.fn() }));
const ids = { userId: "u", profileId: "p", sessionId: "s", speechLocale: "fr-CA" };
const dimension = { status: "correct", explanation: "OK", suggestion: null };
const feedback = { overall_assessment: "OK", grammar: dimension, vocabulary: dimension, clarity: dimension,
  naturalness: dimension, register: dimension, improved_version: "Oui", explanations: [],
  strengths: [], next_recommendation: "Continue" };
const turns = [
  { turn_id: "one", turn_index: 1, learner_text: "Hello", coach_response: "Bonjour!", input_modality: "text", feedback },
  { turn_id: "two", turn_index: 2, learner_text: "More", coach_response: "Comment allez-vous?", input_modality: "text", feedback },
];
let snapshot: SpeechSnapshot;
let listeners: Set<SpeechListener>;
let engine: ReturnType<typeof createBrowserSpeechEngine>;
const speak = vi.fn();
const pause = vi.fn();
const resume = vi.fn();
const stop = vi.fn();
const dispose = vi.fn();
function emit(next: Partial<SpeechSnapshot>) {
  act(() => {
    snapshot = { ...snapshot, ...next };
    listeners.forEach(listener => listener({ ...snapshot }));
  });
}
beforeEach(() => {
  vi.resetAllMocks();
  snapshot = { status: "idle", turnId: null, requestedLocale: null, selectedLocale: null,
    voiceURI: null, voiceMatch: null, error: null };
  listeners = new Set();
  speak.mockImplementation(({ turnId, locale }) => {
    emit({ status: "speaking", turnId, requestedLocale: locale, selectedLocale: locale, voiceMatch: "exact", voiceURI: "voice1" });
    return { ok: true, voiceMatch: "exact", selectedLocale: locale, voiceURI: "voice1" };
  });
  stop.mockImplementation(() => emit({ status: "idle", turnId: null, voiceMatch: null }));
  engine = { available: true, speak, pause, resume, stop, dispose,
    getVoices: () => [], getSnapshot: () => ({ ...snapshot }),
    subscribe: listener => { listeners.add(listener); return () => { listeners.delete(listener); }; } };
  vi.mocked(createBrowserSpeechEngine).mockReturnValue(engine);
  vi.mocked(conversationsApi.list).mockResolvedValue({ items: turns, limit: 50, offset: 0 } as never);
});
function controls(id: string) { return within(screen.getByLabelText(`Audio controls for coach turn ${id}`)); }

describe("VOX-001 playback UI", () => {
  it("shows manual Listen and Repeat for historical responses with no autoplay", async () => {
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Bonjour!");
    expect(controls("one").getByRole("button", { name: "Listen" })).toBeInTheDocument();
    expect(controls("two").getByRole("button", { name: "Repeat" })).toBeInTheDocument();
    expect(speak).not.toHaveBeenCalled();
  });
  it("passes locale and chosen rate to engine, with Pause Resume Stop", async () => {
    const user = userEvent.setup();
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Bonjour!");
    await user.selectOptions(controls("one").getByLabelText("Playback speed"), "0.75");
    await user.click(controls("one").getByRole("button", { name: "Listen" }));
    expect(speak).toHaveBeenCalledWith({ turnId: "one", text: "Bonjour!", locale: "fr-CA", rate: 0.75 });
    await user.click(controls("one").getByRole("button", { name: "Pause" }));
    expect(pause).toHaveBeenCalledOnce();
    emit({ status: "paused" });
    await user.click(controls("one").getByRole("button", { name: "Resume" }));
    expect(resume).toHaveBeenCalledOnce();
    await user.click(controls("one").getByRole("button", { name: "Stop" }));
    expect(stop).toHaveBeenCalled();
  });
  it("switches between turn responses and repeats only the requested turn", async () => {
    const user = userEvent.setup();
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Bonjour!");
    await user.click(controls("one").getByRole("button", { name: "Listen" }));
    await user.click(controls("two").getByRole("button", { name: "Repeat" }));
    expect(speak).toHaveBeenLastCalledWith({ turnId: "two", text: "Comment allez-vous?", locale: "fr-CA", rate: 1 });
  });
  it("stops playback when a session changes and on unmount", async () => {
    const user = userEvent.setup();
    const result = render(<ConversationPanel {...ids} />);
    await screen.findByText("Bonjour!");
    await user.click(controls("one").getByRole("button", { name: "Listen" }));
    const before = stop.mock.calls.length;
    result.rerender(<ConversationPanel {...ids} sessionId="new-session" speechLocale="en-CA" />);
    await waitFor(() => expect(stop.mock.calls.length).toBeGreaterThan(before));
    result.unmount();
    expect(dispose).toHaveBeenCalledOnce();
  });
  it("does not expose playback if browser speech is unsupported", async () => {
    Object.defineProperty(engine, "available", { value: false, configurable: true });
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Bonjour!");
    expect(controls("one").getByRole("button", { name: "Listen" })).toBeDisabled();
    expect(controls("one").getByText("Audio unavailable in this browser.")).toBeInTheDocument();
  });
  it("displays regional fallback and synthesis errors", async () => {
    const user = userEvent.setup();
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Bonjour!");
    await user.click(controls("one").getByRole("button", { name: "Listen" }));
    emit({ voiceMatch: "language-fallback", selectedLocale: "fr-FR" });
    expect(controls("one").getByRole("status")).toHaveTextContent("fr-FR");
    emit({ status: "error", error: "Synthesis failed" });
    expect(controls("one").getByRole("alert")).toHaveTextContent("Synthesis failed");
  });
  it("does not react to superseded turn events", async () => {
    const user = userEvent.setup();
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Bonjour!");
    await user.click(controls("one").getByRole("button", { name: "Listen" }));
    await user.click(controls("two").getByRole("button", { name: "Listen" }));
    expect(controls("two").getByRole("button", { name: "Pause" })).toBeInTheDocument();
    expect(controls("one").queryByRole("button", { name: "Pause" })).not.toBeInTheDocument();
    // Generation-safe event rejection belongs to BrowserSpeechEngine (Step 1 tests).
  });
});
