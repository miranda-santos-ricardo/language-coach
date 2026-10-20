import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeSessionStarted } from "../components/PracticeSessionStarted";
import { api } from "../api/client";
import type { LanguageProfile, PracticeSession } from "../api/types";

vi.mock("../api/client", () => ({ api: { completePracticeSession: vi.fn() } }));
vi.mock("../components/ConversationPanel", () => ({ ConversationPanel: () => <div>Conversation panel</div> }));
vi.mock("../components/VoiceRecorder", () => ({ VoiceRecorder: () => <div>Voice recorder</div> }));

const profile = { id: "profile-1", variant: { display_name: "French — Canada / Québec" } } as LanguageProfile;
const session = {
  id: "session-1", language_profile_id: profile.id, training_mode: "professional",
  effective_cefr: "B2", status: "active",
} as PracticeSession;
const complete = vi.mocked(api.completePracticeSession);

beforeEach(() => {
  vi.resetAllMocks();
  complete.mockResolvedValue({ ...session, status: "completed" });
});

function setup() {
  const onBack = vi.fn();
  render(<PracticeSessionStarted userId="user-1" profile={profile} session={session} onBack={onBack} />);
  return { onBack, user: userEvent.setup() };
}

describe("UX-001 session lifecycle controls", () => {
  it("leaves the practice session active for later resumption without calling complete", async () => {
    const { user, onBack } = setup();
    await user.click(screen.getByRole("button", { name: "Leave & Resume Later" }));
    expect(onBack).toHaveBeenCalledTimes(1);
    expect(complete).not.toHaveBeenCalled();
  });

  it("requires a second confirmation before completing the session", async () => {
    const { user, onBack } = setup();
    await user.click(screen.getByRole("button", { name: "Complete Session" }));
    expect(complete).not.toHaveBeenCalled();
    expect(screen.getByRole("group", { name: "Confirm session completion" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(complete).not.toHaveBeenCalled();
    expect(onBack).not.toHaveBeenCalled();
  });

  it("completes via existing API and navigates away only when server confirms", async () => {
    const { user, onBack } = setup();
    await user.click(screen.getByRole("button", { name: "Complete Session" }));
    await user.click(screen.getByRole("button", { name: "Confirm completion" }));
    await waitFor(() => expect(complete).toHaveBeenCalledWith("user-1", profile.id, session.id));
    await waitFor(() => expect(onBack).toHaveBeenCalledTimes(1));
  });

  it("prevents duplicate completion requests while pending", async () => {
    let resolve!: (value: PracticeSession) => void;
    complete.mockImplementation(() => new Promise(r => { resolve = r; }));
    const { user, onBack } = setup();
    await user.click(screen.getByRole("button", { name: "Complete Session" }));
    await user.click(screen.getByRole("button", { name: "Confirm completion" }));
    expect(screen.getByRole("button", { name: "Completing…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Leave & Resume Later" })).toBeDisabled();
    expect(complete).toHaveBeenCalledTimes(1);
    resolve({ ...session, status: "completed" });
    await waitFor(() => expect(onBack).toHaveBeenCalledTimes(1));
  });

  it("keeps the session open and shows the error when the API fails", async () => {
    complete.mockRejectedValueOnce(new Error("Server unavailable"));
    const { user, onBack } = setup();
    await user.click(screen.getByRole("button", { name: "Complete Session" }));
    await user.click(screen.getByRole("button", { name: "Confirm completion" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Server unavailable");
    expect(onBack).not.toHaveBeenCalled();
    expect(screen.getByText("Conversation panel")).toBeInTheDocument();
  });

  it("rejects a response that does not confirm COMPLETED for this session", async () => {
    complete.mockResolvedValueOnce({ ...session, status: "active" });
    const { user, onBack } = setup();
    await user.click(screen.getByRole("button", { name: "Complete Session" }));
    await user.click(screen.getByRole("button", { name: "Confirm completion" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("did not confirm");
    expect(onBack).not.toHaveBeenCalled();
  });
});
