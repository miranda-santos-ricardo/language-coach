import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";

afterEach(() => vi.restoreAllMocks());

it("POSTs session completion to the existing endpoint", async () => {
  const payload = { id: "session-1", status: "completed" };
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }),
  );
  const response = await api.completePracticeSession("user-1", "profile-1", "session-1");
  expect(response).toEqual(payload);
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/users/user-1/language-profiles/profile-1/sessions/session-1/complete"),
    expect.objectContaining({ method: "POST" }),
  );
});
