import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationPanel, mergeConversationTurns } from "../components/ConversationPanel";
import { conversationsApi } from "../api/conversations";
import type { ConversationTurnDetail } from "../api/conversations";

vi.mock("../api/conversations", () => ({ conversationsApi: { list: vi.fn(), submit: vi.fn(), get: vi.fn() } }));
const ids = { userId: "u", profileId: "p", sessionId: "session-a" };
const dimension = { status: "correct" as const, explanation: "OK", suggestion: null };
const feedback = { overall_assessment: "Good", grammar: dimension, vocabulary: dimension, clarity: dimension,
  naturalness: dimension, register: dimension, improved_version: "Fine", explanations: [], strengths: [], next_recommendation: "Continue" };
const turn = (index: number, session = "a"): ConversationTurnDetail => ({
  turn_id: `${session}-${index}`, turn_index: index, input_modality: "text", learner_text: `Learner ${session}-${index}`,
  coach_response: `Coach ${session}-${index}`, created_at: "2026-10-01T00:00:00Z", feedback,
});
const page = (items: ConversationTurnDetail[], offset = 0) => ({ items, offset, limit: 50 });
const pending = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(r => { resolve = r; });
  return { promise, resolve };
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(conversationsApi.list).mockResolvedValue(page([]));
});

describe("multi-turn ordering, pagination and isolation", () => {
  it("sorts and deduplicates overlapping turn pages by turn_id", () => {
    expect(mergeConversationTurns([turn(2), turn(1)], [turn(2), turn(3)]).map(t => t.turn_index))
      .toEqual([1, 2, 3]);
    expect(mergeConversationTurns([turn(1)], [turn(4)], true).map(t => t.turn_index)).toEqual([4]);
  });

  it("loads a second page, keeps chronological order and deduplicates overlap", async () => {
    const first = Array.from({ length: 50 }, (_, i) => turn(50 - i));
    vi.mocked(conversationsApi.list).mockResolvedValueOnce(page(first))
      .mockResolvedValueOnce(page([turn(50), turn(51)], 50));
    const user = userEvent.setup();
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Coach a-1");
    await user.click(screen.getByRole("button", { name: "Load more turns" }));
    await screen.findByText("Coach a-51");
    const rows = [...screen.getByRole("list", { name: "Conversation history" }).children];
    expect(rows).toHaveLength(51);
    expect(rows[0]).toHaveTextContent("Learner a-1");
    expect(rows[50]).toHaveTextContent("Learner a-51");
    expect(conversationsApi.list).toHaveBeenNthCalledWith(2, ids, 50, 50);
  });

  it("ignores a stale history response after switching sessions", async () => {
    const oldRequest = pending<ReturnType<typeof page>>();
    vi.mocked(conversationsApi.list).mockReturnValueOnce(oldRequest.promise).mockResolvedValueOnce(page([turn(1, "b")]));
    const { rerender } = render(<ConversationPanel {...ids} />);
    rerender(<ConversationPanel {...ids} sessionId="session-b" />);
    await screen.findByText("Coach b-1");
    oldRequest.resolve(page([turn(1, "a")]));
    await waitFor(() => expect(screen.getByRole("list", { name: "Conversation history" })).not.toHaveTextContent("Coach a-1"));
    expect(screen.getByRole("list", { name: "Conversation history" })).toHaveTextContent("Coach b-1");
  });

  it("does not display an old profile's response after a profile switch", async () => {
    const oldRequest = pending<ReturnType<typeof page>>();
    vi.mocked(conversationsApi.list).mockReturnValueOnce(oldRequest.promise).mockResolvedValueOnce(page([turn(2, "b")]));
    const { rerender } = render(<ConversationPanel {...ids} />);
    rerender(<ConversationPanel {...ids} profileId="different-profile" />);
    await screen.findByText("Coach b-2");
    oldRequest.resolve(page([turn(1, "a")]));
    await waitFor(() => expect(screen.queryByText("Coach a-1")).not.toBeInTheDocument());
  });

  it("prevents repeated pagination clicks while a page is pending", async () => {
    const first = Array.from({ length: 50 }, (_, i) => turn(i + 1));
    const next = pending<ReturnType<typeof page>>();
    vi.mocked(conversationsApi.list).mockResolvedValueOnce(page(first)).mockReturnValueOnce(next.promise);
    const user = userEvent.setup();
    render(<ConversationPanel {...ids} />);
    await screen.findByText("Coach a-50");
    await user.click(screen.getByRole("button", { name: "Load more turns" }));
    expect(screen.getByRole("button", { name: "Load more turns" })).toBeDisabled();
    expect(conversationsApi.list).toHaveBeenCalledTimes(2);
    next.resolve(page([], 50));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Load more turns" })).not.toBeInTheDocument());
  });
});
