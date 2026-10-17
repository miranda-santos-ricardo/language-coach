import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationPanel } from "../components/ConversationPanel";
import { conversationsApi } from "../api/conversations";

vi.mock("../api/conversations", () => ({ conversationsApi: { list: vi.fn(), submit: vi.fn(), get: vi.fn() } }));
const ids = { userId: "u", profileId: "p", sessionId: "s" };
const dim = { status: "correct" as const, explanation: "Looks good", suggestion: null };
const feedback = {
  overall_assessment: "Clear communication", grammar: dim, vocabulary: dim, clarity: dim,
  naturalness: dim, register: dim, improved_version: "Bonjour", explanations: [],
  strengths: ["Clear"], next_recommendation: "Practice again",
};
const turn = {
  turn_id: "turn-1", turn_index: 1, input_modality: "text" as const,
  learner_text: "Bonjour", coach_response: "Salut!", created_at: "2026-10-01T00:00:00Z", feedback,
};
const submission = { turn_id: "turn-1", turn_index: 1, coach_response: "Salut!", feedback, replayed: false, prompt_version: "coach-v2", model: "mock" };

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(conversationsApi.list).mockResolvedValue({ items: [], limit: 50, offset: 0 });
  vi.mocked(conversationsApi.submit).mockResolvedValue(submission);
});

describe("ConversationPanel", () => {
  it("loads previous turns and displays expandable structured feedback", async () => {
    vi.mocked(conversationsApi.list).mockResolvedValue({ items: [turn], limit: 50, offset: 0 });
    const user = userEvent.setup();
    render(<ConversationPanel {...ids} />);
    await waitFor(() => {
      const history = screen.getByRole("list", { name: "Conversation history" });
      expect(history.querySelector("li > p")).toHaveTextContent("You: Bonjour");
    });
    expect(screen.getByText("Salut!")).toBeInTheDocument();
    await user.click(screen.getByText("View language feedback"));
    expect(screen.getByText("Clear communication")).toBeInTheDocument();
    expect(conversationsApi.list).toHaveBeenCalledWith(ids, 50, 0);
  });

  it("submits a typed utterance with request id and reloads history", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationsApi.list)
      .mockResolvedValueOnce({ items: [], limit: 50, offset: 0 })
      .mockResolvedValue({ items: [turn], limit: 50, offset: 0 });
    render(<ConversationPanel {...ids} />);
    await user.type(screen.getByLabelText("Your message"), "Bonjour");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    await waitFor(() => expect(conversationsApi.submit).toHaveBeenCalledTimes(1));
    const payload = vi.mocked(conversationsApi.submit).mock.calls[0][1];
    expect(payload.text).toBe("Bonjour");
    expect(payload.input_modality).toBe("text");
    expect(payload.client_request_id).toMatch(/^[a-f\d-]{36}$/i);
    expect(await screen.findByText("Salut!")).toBeInTheDocument();
    expect(screen.getByLabelText("Your message")).toHaveValue("");
  });

  it("keeps draft and reuses request id on failed request retry", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationsApi.submit).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(submission);
    render(<ConversationPanel {...ids} />);
    await user.type(screen.getByLabelText("Your message"), "Bonjour");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("kept");
    expect(screen.getByLabelText("Your message")).toHaveValue("Bonjour");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    await waitFor(() => expect(conversationsApi.submit).toHaveBeenCalledTimes(2));
    expect(vi.mocked(conversationsApi.submit).mock.calls[0][1].client_request_id)
      .toBe(vi.mocked(conversationsApi.submit).mock.calls[1][1].client_request_id);
  });

  it("prevents duplicate submission while pending", async () => {
    const user = userEvent.setup();
    let complete!: (value: typeof submission) => void;
    vi.mocked(conversationsApi.submit).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
    render(<ConversationPanel {...ids} />);
    await user.type(screen.getByLabelText("Your message"), "Bonjour");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(conversationsApi.submit).toHaveBeenCalledTimes(1);
    complete(submission);
    await waitFor(() => expect(screen.getByRole("button", { name: "Send to Coach" })).toBeDisabled());
  });

  it("keeps the response visible if history refresh fails", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationsApi.list).mockResolvedValueOnce({ items: [], limit: 50, offset: 0 }).mockRejectedValueOnce(new Error("Cannot refresh"));
    render(<ConversationPanel {...ids} />);
    await user.type(screen.getByLabelText("Your message"), "Bonjour");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    expect(await screen.findByText("Salut!")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot refresh");
  });

  it("reports history failure and allows retry", async () => {
    const user = userEvent.setup();
    const listMock = vi.mocked(conversationsApi.list);

    listMock
      .mockRejectedValueOnce(new Error("History unavailable"))
      .mockResolvedValue({ items: [turn], limit: 50, offset: 0 });

    const { container } = render(<ConversationPanel {...ids} />);

    expect(await screen.findByRole("alert"))
      .toHaveTextContent("History unavailable");

    await user.click(screen.getByRole("button", { name: "Retry history" }));

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledTimes(2);
    });

    const secondCall = listMock.mock.results[1];
    expect(secondCall?.type).toBe("return");

    const response = await secondCall.value;
    expect(response.items).toHaveLength(1);
    expect(response.items[0].learner_text).toBe("Bonjour");

    // Diagnose the rendered UI without assuming a particular ARIA role or CSS selector.
    try {
      await waitFor(() => {
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(container).toHaveTextContent("Bonjour");
      });
    } catch (error) {
      console.error("[retry diagnostics] list call count:", listMock.mock.calls.length);
      console.error("[retry diagnostics] list call arguments:", listMock.mock.calls);
      console.error("[retry diagnostics] second API response:", JSON.stringify(response));
      console.error("[retry diagnostics] rendered DOM:", container.innerHTML);
      throw error;
    }
  });

  it("fills the editor with a voice transcript without auto-submitting", async () => {
    const { rerender } = render(<ConversationPanel {...ids} />);
    rerender(<ConversationPanel {...ids} voiceDraft={{ text: "Bonjour de Québec", revision: 1 }} />);
    expect(screen.getByLabelText("Your message")).toHaveValue("Bonjour de Québec");
    expect(screen.getByText(/Voice transcript — review or edit/)).toBeInTheDocument();
    expect(conversationsApi.submit).not.toHaveBeenCalled();
  });

  it("sends an edited voice transcript as voice only after clicking send", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ConversationPanel {...ids} />);
    rerender(<ConversationPanel {...ids} voiceDraft={{ text: "Bonjour", revision: 1 }} />);
    const editor = screen.getByLabelText("Your message");
    await user.type(editor, " à tous");
    expect(conversationsApi.submit).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    await waitFor(() => expect(conversationsApi.submit).toHaveBeenCalledTimes(1));
    expect(vi.mocked(conversationsApi.submit).mock.calls[0][1]).toMatchObject({
      text: "Bonjour à tous", input_modality: "voice",
    });
  });

  it("preserves voice modality and id after a failed send", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationsApi.submit)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(submission);
    const { rerender } = render(<ConversationPanel {...ids} />);
    rerender(<ConversationPanel {...ids} voiceDraft={{ text: "Parlons français", revision: 1 }} />);
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("kept");
    expect(screen.getByLabelText("Your message")).toHaveValue("Parlons français");
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    await waitFor(() => expect(conversationsApi.submit).toHaveBeenCalledTimes(2));
    const calls = vi.mocked(conversationsApi.submit).mock.calls;
    expect(calls[0][1].input_modality).toBe("voice");
    expect(calls[1][1].input_modality).toBe("voice");
    expect(calls[0][1].client_request_id).toBe(calls[1][1].client_request_id);
  });

  it("keeps the submit button disabled during a pending voice request", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationsApi.submit).mockImplementation(() => new Promise(() => {}));
    const { rerender } = render(<ConversationPanel {...ids} />);
    rerender(<ConversationPanel {...ids} voiceDraft={{ text: "Bonjour", revision: 1 }} />);
    await user.click(screen.getByRole("button", { name: "Send to Coach" }));
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(conversationsApi.submit).toHaveBeenCalledTimes(1);
  });

});
