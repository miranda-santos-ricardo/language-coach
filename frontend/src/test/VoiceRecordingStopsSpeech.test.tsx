import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { VoiceRecorder } from "../components/VoiceRecorder";

const startRecording = vi.fn().mockResolvedValue(undefined);
vi.mock("../hooks/useAudioRecorder", () => ({
  useAudioRecorder: () => ({ status: "IDLE", recordedAudio: null, error: null, startRecording,
    stopRecording: vi.fn(), reset: vi.fn() }),
}));

describe("VOX-001 microphone / speaker coordination", () => {
  it("stops the coach audio before starting microphone capture", async () => {
    const order: string[] = [];
    const onRecordingStart = vi.fn(() => order.push("stop-coach"));
    startRecording.mockImplementationOnce(() => { order.push("start-mic"); return Promise.resolve(); });
    render(<VoiceRecorder userId="u" profileId="p" practiceSessionId="s" onRecordingStart={onRecordingStart} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Start recording" }));
    expect(order).toEqual(["stop-coach", "start-mic"]);
  });
});
