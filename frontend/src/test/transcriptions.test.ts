import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { api, ApiError } from "../api/client";

const USER_ID = "user-123";
const PROFILE_ID = "profile-456";
const SESSION_ID = "session-789";

const EXPECTED_PATH =
  `/users/${USER_ID}` +
  `/language-profiles/${PROFILE_ID}` +
  `/sessions/${SESSION_ID}` +
  `/transcriptions`;

function createAudioBlob(): Blob {
  return new Blob(["fake-audio-data"], {
    type: "audio/webm;codecs=opus",
  });
}

describe("api.transcribeAudio", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends audio to the correct session endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          transcript: "Bonjour, comment allez-vous?",
          language: "fr",
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    vi.stubGlobal("fetch", fetchMock);

    await api.transcribeAudio(
      USER_ID,
      PROFILE_ID,
      SESSION_ID,
      createAudioBlob(),
      "webm",
    );

    expect(fetchMock).toHaveBeenCalledOnce();

    const [url, options] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];

    expect(url).toBe(
      `${import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"}${EXPECTED_PATH}`,
    );

    expect(options.method).toBe("POST");
  });

  it("uploads the audio using FormData", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          transcript: "Hello.",
          language: "en",
        }),
        { status: 200 },
      ),
    );

    vi.stubGlobal("fetch", fetchMock);

    await api.transcribeAudio(
      USER_ID,
      PROFILE_ID,
      SESSION_ID,
      createAudioBlob(),
      "webm",
    );

    const [, options] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];

    expect(options.body).toBeInstanceOf(FormData);

    const formData = options.body as FormData;
    const uploadedFile = formData.get("audio");

    expect(uploadedFile).toBeInstanceOf(File);

    const file = uploadedFile as File;

    expect(file.name).toBe("recording.webm");
    expect(file.type).toBe("audio/webm;codecs=opus");
    expect(await file.text()).toBe("fake-audio-data");
  });

  it("does not set JSON Content-Type for multipart upload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          transcript: "Hello.",
          language: "en",
        }),
        { status: 200 },
      ),
    );

    vi.stubGlobal("fetch", fetchMock);

    await api.transcribeAudio(
      USER_ID,
      PROFILE_ID,
      SESSION_ID,
      createAudioBlob(),
      "webm",
    );

    const [, options] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];

    const headers = new Headers(options.headers);

    expect(headers.has("Content-Type")).toBe(false);
  });

  it("returns the transcript and language from the backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            transcript: "Je travaille dans une banque.",
            language: "fr",
          }),
          { status: 200 },
        ),
      ),
    );

    const result = await api.transcribeAudio(
      USER_ID,
      PROFILE_ID,
      SESSION_ID,
      createAudioBlob(),
      "webm",
    );

    expect(result).toEqual({
      transcript: "Je travaille dans une banque.",
      language: "fr",
    });
  });

  it("throws ApiError when the session is inactive", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "Practice session is not active.",
          }),
          {
            status: 409,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      ),
    );

    await expect(
      api.transcribeAudio(
        USER_ID,
        PROFILE_ID,
        SESSION_ID,
        createAudioBlob(),
        "webm",
      ),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      message: "Practice session is not active.",
    });
  });

  it.each([
    [400, "Invalid audio upload"],
    [413, "Audio file too large"],
    [415, "Unsupported audio format"],
    [503, "Transcription service unavailable"],
    [504, "Transcription request timed out"],
  ])(
    "propagates HTTP %i as ApiError",
    async (status, detail) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(
            JSON.stringify({ detail }),
            {
              status,
              headers: {
                "Content-Type": "application/json",
              },
            },
          ),
        ),
      );

      await expect(
        api.transcribeAudio(
          USER_ID,
          PROFILE_ID,
          SESSION_ID,
          createAudioBlob(),
          "webm",
        ),
      ).rejects.toMatchObject({
        name: "ApiError",
        status,
        message: detail,
      });
    },
  );

  it("uses a fallback message when the error response is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Service unavailable", {
          status: 503,
        }),
      ),
    );

    await expect(
      api.transcribeAudio(
        USER_ID,
        PROFILE_ID,
        SESSION_ID,
        createAudioBlob(),
        "webm",
      ),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("propagates network failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(
        new TypeError("Failed to fetch"),
      ),
    );

    await expect(
      api.transcribeAudio(
        USER_ID,
        PROFILE_ID,
        SESSION_ID,
        createAudioBlob(),
        "webm",
      ),
    ).rejects.toThrow("Failed to fetch");
  });
});