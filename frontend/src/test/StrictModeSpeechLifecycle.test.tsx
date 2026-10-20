import { StrictMode } from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationPanel } from "../components/ConversationPanel";
import { conversationsApi } from "../api/conversations";
import { createBrowserSpeechEngine } from "../services/browserSpeech";
import type { SpeechSnapshot } from "../services/browserSpeech";

vi.mock("../api/conversations", () => ({ conversationsApi: { list: vi.fn(), submit: vi.fn() } }));
vi.mock("../services/browserSpeech", () => ({ createBrowserSpeechEngine: vi.fn() }));

const dimension = { status: "correct", explanation: "OK", suggestion: null };
const feedback = { overall_assessment: "OK", grammar: dimension, vocabulary: dimension,
  clarity: dimension, naturalness: dimension, register: dimension, improved_version: "Bonjour",
  explanations: [], strengths: [], next_recommendation: "Continue" };
const ids = { userId: "u", profileId: "p", sessionId: "s", speechLocale: "fr-CA" };
const disposeSpies: ReturnType<typeof vi.fn>[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  disposeSpies.length = 0;
  vi.mocked(conversationsApi.list).mockResolvedValue({
    items: [{ turn_id: "one", turn_index: 1, learner_text: "Salut", coach_response: "Bonjour", feedback }],
    limit: 50, offset: 0,
  } as never);
  vi.mocked(createBrowserSpeechEngine).mockImplementation(() => {
    let disposed = false;
    const dispose = vi.fn(() => { disposed = true; });
    disposeSpies.push(dispose);
    const snapshot: SpeechSnapshot = { status: "idle", turnId: null, requestedLocale: null,
      selectedLocale: null, voiceURI: null, voiceMatch: null, error: null };
    return {
      get available() { return !disposed; },
      getSnapshot: () => snapshot, getVoices: () => [],
      speak: vi.fn(() => ({ ok: true as const, voiceMatch: "exact" as const, selectedLocale: "fr-CA", voiceURI: "fr-ca-1" })),
      pause: vi.fn(), resume: vi.fn(), stop: vi.fn(),
      subscribe: vi.fn(() => () => {}), dispose,
    };
  });
});
afterEach(() => vi.restoreAllMocks());

describe("Browser TTS lifecycle under React StrictMode", () => {
  it("keeps the active engine available after StrictMode replays effects", async () => {
    const view = render(<StrictMode><ConversationPanel {...ids}/></StrictMode>);
    const control = await screen.findByRole("group", { name: /Coach voice preferences/i });
    expect(control).toBeInTheDocument();
    const row = await screen.findByRole("list", { name: "Conversation history" });
    const listen = within(row).getByRole("button", { name: "Listen" });
    expect(listen).toBeEnabled();
    expect(screen.queryByText("Audio unavailable in this browser.")).not.toBeInTheDocument();
    view.unmount();
    await act(async () => { await Promise.resolve(); });
    expect(disposeSpies.some(spy => spy.mock.calls.length > 0)).toBe(true);
  });
});
