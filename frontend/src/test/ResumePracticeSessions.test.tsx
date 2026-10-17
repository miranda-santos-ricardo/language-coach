import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResumePracticeSessions } from "../components/ResumePracticeSessions";
import { api } from "../api/client";
import type { PracticeSession } from "../api/types";

vi.mock("../api/client", () => ({ api: { listPracticeSessions: vi.fn(), getPracticeSession: vi.fn() } }));
const active = {
  id: "session-a", language_profile_id: "profile-a", status: "active", training_mode: "conversation",
  effective_cefr: "B2", started_at: "2026-10-10T12:00:00Z",
} as PracticeSession;
const old = { ...active, id: "session-old", status: "completed", started_at: "2026-09-10T12:00:00Z" } as PracticeSession;
const params = { userId: "user-a", profileId: "profile-a" };

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.listPracticeSessions).mockResolvedValue([active, old]);
  vi.mocked(api.getPracticeSession).mockResolvedValue(active);
});

describe("ResumePracticeSessions", () => {
  it("loads only after explicit request and filters completed sessions", async () => {
    const user = userEvent.setup();
    render(<ResumePracticeSessions {...params} onResume={vi.fn()} />);
    expect(api.listPracticeSessions).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Find active sessions" }));
    expect(await screen.findByRole("button", { name: "Resume session" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(api.listPracticeSessions).toHaveBeenCalledWith("user-a", "profile-a");
  });

  it("fetches server session again before resuming", async () => {
    const user = userEvent.setup();
    const onResume = vi.fn();
    render(<ResumePracticeSessions {...params} onResume={onResume} />);
    await user.click(screen.getByRole("button", { name: "Find active sessions" }));
    await user.click(await screen.findByRole("button", { name: "Resume session" }));
    await waitFor(() => expect(onResume).toHaveBeenCalledWith(active));
    expect(api.getPracticeSession).toHaveBeenCalledWith("user-a", "profile-a", "session-a");
  });

  it("refuses a session that was closed after listing", async () => {
    const user = userEvent.setup();
    const onResume = vi.fn();
    vi.mocked(api.getPracticeSession).mockResolvedValue({ ...active, status: "completed" });
    render(<ResumePracticeSessions {...params} onResume={onResume} />);
    await user.click(screen.getByRole("button", { name: "Find active sessions" }));
    await user.click(await screen.findByRole("button", { name: "Resume session" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no longer active");
    expect(onResume).not.toHaveBeenCalled();
  });

  it("does not expose sessions from another profile", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPracticeSessions).mockResolvedValue([{ ...active, language_profile_id: "another-profile" }]);
    render(<ResumePracticeSessions {...params} onResume={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Find active sessions" }));
    expect(await screen.findByText("No active sessions for this profile.")).toBeInTheDocument();
  });

  it("handles API failure and allows retry", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPracticeSessions).mockRejectedValueOnce(new Error("Network unavailable")).mockResolvedValue([active]);
    render(<ResumePracticeSessions {...params} onResume={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Find active sessions" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Network unavailable");
    await user.click(screen.getByRole("button", { name: "Refresh active sessions" }));
    expect(await screen.findByRole("button", { name: "Resume session" })).toBeInTheDocument();
  });
});
