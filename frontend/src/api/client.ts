import type {
  CommunicationRegister,
  Language,
  LanguageProfile,
  LanguageProfilePayload,
  LanguageVariant,
  User,
  PracticeSession,
  PracticeSessionPayload,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(payload: unknown, fallback: string): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload
  ) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (
        typeof first === "object" &&
        first !== null &&
        "msg" in first &&
        typeof (first as { msg: unknown }).msg === "string"
      ) {
        return (first as { msg: string }).msg;
      }
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // The fallback below is enough when the response has no JSON body.
    }
    throw new ApiError(
      errorMessage(payload, `Request failed with status ${response.status}`),
      response.status,
    );
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  listUsers: () => request<User[]>("/users"),
  createUser: (displayName: string) =>
    request<User>("/users", {
      method: "POST",
      body: JSON.stringify({ display_name: displayName }),
    }),

  listLanguages: () => request<Language[]>("/languages"),
  listVariants: (languageCode: string) =>
    request<LanguageVariant[]>(
      `/languages/${encodeURIComponent(languageCode)}/variants`,
    ),
  listRegisters: () =>
    request<CommunicationRegister[]>("/communication-registers"),

  listProfiles: (userId: string) =>
    request<LanguageProfile[]>(`/users/${userId}/language-profiles`),
  createProfile: (userId: string, payload: LanguageProfilePayload) =>
    request<LanguageProfile>(`/users/${userId}/language-profiles`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProfile: (
    userId: string,
    profileId: string,
    payload: LanguageProfilePayload,
  ) =>
    request<LanguageProfile>(
      `/users/${userId}/language-profiles/${profileId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    ),
  createPracticeSession: (
  userId: string,
  profileId: string,
  payload: PracticeSessionPayload,
) =>
  request<PracticeSession>(
    `/users/${userId}/language-profiles/${profileId}/sessions`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  ),

listPracticeSessions: (
  userId: string,
  profileId: string,
) =>
  request<PracticeSession[]>(
    `/users/${userId}/language-profiles/${profileId}/sessions`,
  ),

getPracticeSession: (
  userId: string,
  profileId: string,
  sessionId: string,
) =>
  request<PracticeSession>(
    `/users/${userId}/language-profiles/${profileId}/sessions/${sessionId}`,
  ),
};