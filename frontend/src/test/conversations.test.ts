import { afterEach, describe, expect, it, vi } from "vitest";
import { conversationsApi } from "../api/conversations";
import { ApiError } from "../api/client";
const context = { userId: "u", profileId: "p", sessionId: "s" };
afterEach(() => vi.unstubAllGlobals());
describe("conversationsApi", () => {
  it("POSTs payload as JSON to the correct path", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ turn_id: "t" }) });
    vi.stubGlobal("fetch", fetchMock);
    const payload = { text: "Bonjour", input_modality: "text" as const, client_request_id: "uuid" };
    await conversationsApi.submit(context, payload);
    expect(fetchMock.mock.calls[0][0]).toContain("/users/u/language-profiles/p/sessions/s/turns");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify(payload) });
  });
  it("GETs paginated history and turn details", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) });
    vi.stubGlobal("fetch", fetchMock);
    await conversationsApi.list(context, 10, 20);
    await conversationsApi.get(context, "abc");
    expect(fetchMock.mock.calls[0][0]).toContain("/turns?limit=10&offset=20");
    expect(fetchMock.mock.calls[1][0]).toContain("/turns/abc");
  });
  it("propagates sanitized HTTP error details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: "Practice session is not active." }) }));
    await expect(conversationsApi.list(context)).rejects.toEqual(new ApiError("Practice session is not active.", 409));
  });
});
