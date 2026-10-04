import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VoiceRecorder } from "../components/VoiceRecorder";

class MockMediaRecorder {
  static isTypeSupported = vi.fn(
    (mimeType: string) => mimeType === "audio/webm;codecs=opus",
  );

  state: RecordingState = "inactive";
  mimeType: string;

  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(
    _stream: MediaStream,
    options?: MediaRecorderOptions,
  ) {
    this.mimeType = options?.mimeType ?? "";
  }

  start() {
    this.state = "recording";
  }

  stop() {
    if (this.state !== "recording") {
      return;
    }

    this.state = "inactive";

    const audioBlob = new Blob(
      ["fake-audio-data"],
      {
        type: this.mimeType,
      },
    );

    this.ondataavailable?.(
      new BlobEvent("dataavailable", {
        data: audioBlob,
      }),
    );

    this.onstop?.();
  }
}

function createMockStream() {
  const stopTrack = vi.fn();

  const stream = {
    getTracks: () => [
      {
        stop: stopTrack,
      },
    ],
  } as unknown as MediaStream;

  return {
    stream,
    stopTrack,
  };
}

describe("VoiceRecorder", () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });

    Object.defineProperty(globalThis, "MediaRecorder", {
      configurable: true,
      writable: true,
      value: MockMediaRecorder,
    });

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: vi.fn(() => "blob:mock-audio"),
    });

    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("starts in the idle state", () => {
    render(<VoiceRecorder />);

    expect(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Record your voice to start practicing.",
      ),
    ).toBeInTheDocument();
  });

  it("starts recording after microphone permission is granted", async () => {
    const user = userEvent.setup();
    const { stream } = createMockStream();

    const getUserMedia = vi.fn().mockResolvedValue(stream);

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia,
      },
    });

    render(<VoiceRecorder />);

    await user.click(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    );

    expect(getUserMedia).toHaveBeenCalledWith({
      audio: true,
    });

    expect(
      await screen.findByText("Recording..."),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Stop recording",
      }),
    ).toBeInTheDocument();
  });

  it("creates a playable recording after stopping", async () => {
    const user = userEvent.setup();
    const { stream, stopTrack } = createMockStream();

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });

    render(<VoiceRecorder />);

    await user.click(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    );

    await screen.findByText("Recording...");

    await user.click(
      screen.getByRole("button", {
        name: "Stop recording",
      }),
    );

    expect(
      await screen.findByText("Recording ready."),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Format: audio/webm;codecs=opus",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Record again",
      }),
    ).toBeInTheDocument();

    expect(URL.createObjectURL).toHaveBeenCalled();

    expect(stopTrack).toHaveBeenCalled();
  });

  it("returns to idle when Record again is clicked", async () => {
    const user = userEvent.setup();
    const { stream } = createMockStream();

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });

    render(<VoiceRecorder />);

    await user.click(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    );

    await screen.findByText("Recording...");

    await user.click(
      screen.getByRole("button", {
        name: "Stop recording",
      }),
    );

    await screen.findByText("Recording ready.");

    await user.click(
      screen.getByRole("button", {
        name: "Record again",
      }),
    );

    expect(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Recording ready."),
    ).not.toBeInTheDocument();
  });

  it("shows an error when microphone permission is denied", async () => {
    const user = userEvent.setup();

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockRejectedValue(
          new DOMException(
            "Permission denied",
            "NotAllowedError",
          ),
        ),
      },
    });

    render(<VoiceRecorder />);

    await user.click(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    );

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(
      "Microphone permission was denied.",
    );

    expect(
      screen.getByRole("button", {
        name: "Try again",
      }),
    ).toBeInTheDocument();
  });

  it("shows an error when the page is not a secure context", async () => {
    const user = userEvent.setup();

    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: false,
    });

    render(<VoiceRecorder />);

    await user.click(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    );

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(
      "Microphone recording requires a secure browser context.",
    );
  });

  it("releases the object URL when the recording is discarded", async () => {
    const user = userEvent.setup();
    const { stream } = createMockStream();

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });

    render(<VoiceRecorder />);

    await user.click(
      screen.getByRole("button", {
        name: "Start recording",
      }),
    );

    await screen.findByText("Recording...");

    await user.click(
      screen.getByRole("button", {
        name: "Stop recording",
      }),
    );

    await screen.findByText("Recording ready.");

    await waitFor(() => {
      expect(URL.createObjectURL).toHaveBeenCalledWith(
        expect.any(Blob),
      );
    });

    await user.click(
      screen.getByRole("button", {
        name: "Record again",
      }),
    );

    await waitFor(() => {
      expect(URL.revokeObjectURL).toHaveBeenCalledWith(
        "blob:mock-audio",
      );
    });
  });
});