/** Isolated pilot API. Never uses the legacy unguarded API client. */
import { isValidSession, type AuthTokens } from './oidc';
import type { User, LanguageProfile, PracticeSession, PracticeSessionPayload } from '../api/types';
import type { TurnSubmission, TurnSubmitted, ConversationTurnPage, ConversationTurnDetail } from '../api/conversations';

export class PilotApiError extends Error {
  constructor(public readonly status: number) {
    super(status === 401 ? 'Authentication expired or revoked' : status === 403 ? 'Access denied' : status === 404 ? 'Resource unavailable' : 'Pilot API request failed');
  }
}

export function createPilotApi(baseUrl: string, tokens: AuthTokens, fetcher: typeof fetch = fetch) {
  const origin = new URL(baseUrl);
  if (origin.username || origin.password || origin.hash || origin.search ||
      (origin.protocol !== 'https:' && !(origin.protocol === 'http:' && ['localhost','127.0.0.1'].includes(origin.hostname)))) {
    throw new Error('Pilot API requires trusted HTTPS origin');
  }
  const base = origin.origin;
  async function request<T>(path: string, signal?: AbortSignal, method: 'GET' | 'POST' = 'GET', body?: unknown): Promise<T> {
    if (!isValidSession(tokens)) throw new PilotApiError(401);
    if (!path.startsWith('/') || path.startsWith('//')) throw new Error('Invalid API path');
    const response = await fetcher(`${base}${path}`, {
      method, headers: { Authorization: `Bearer ${tokens.accessToken}`, Accept: 'application/json', ...(method === 'POST' && body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      ...(method === 'POST' && body !== undefined ? { body: JSON.stringify(body) } : {}),
      credentials: 'omit', cache: 'no-store', redirect: 'error', signal,
    });
    if (!response.ok) throw new PilotApiError(response.status);
    return (await response.json()) as T;
  }
  function sessionPath(userId: string, profileId: string, sessionId?: string): string {
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuid.test(userId) || !uuid.test(profileId) || (sessionId !== undefined && !uuid.test(sessionId))) {
      throw new Error('Invalid internal resource ID');
    }
    const root = `/users/${userId}/language-profiles/${profileId}/sessions`;
    return sessionId ? `${root}/${sessionId}` : root;
  }
  function turnsPath(userId: string, profileId: string, sessionId: string, turnId?: string): string {
    const base = `${sessionPath(userId, profileId, sessionId)}/turns`;
    if (turnId !== undefined && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(turnId)) {
      throw new Error('Invalid internal resource ID');
    }
    return turnId ? `${base}/${turnId}` : base;
  }
  return {
    turns: {
      list: (userId: string, profileId: string, sessionId: string, limit = 50, offset = 0, signal?: AbortSignal) => {
        if (!Number.isInteger(limit) || limit < 1 || limit > 100 || !Number.isInteger(offset) || offset < 0) throw new Error('Invalid pagination');
        return request<ConversationTurnPage>(`${turnsPath(userId, profileId, sessionId)}?limit=${limit}&offset=${offset}`, signal);
      },
      get: (userId: string, profileId: string, sessionId: string, turnId: string, signal?: AbortSignal) =>
        request<ConversationTurnDetail>(turnsPath(userId, profileId, sessionId, turnId), signal),
      submit: (userId: string, profileId: string, sessionId: string, payload: TurnSubmission, signal?: AbortSignal) => {
        if (payload.input_modality !== 'text' || !payload.text.trim() || payload.text.length > 4000 ||
            !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(payload.client_request_id)) {
          throw new Error('Invalid text turn submission');
        }
        return request<TurnSubmitted>(turnsPath(userId, profileId, sessionId), signal, 'POST', payload);
      },
    },
    sessions: {
      list: (userId: string, profileId: string, signal?: AbortSignal) => request<PracticeSession[]>(sessionPath(userId, profileId), signal),
      get: (userId: string, profileId: string, sessionId: string, signal?: AbortSignal) => request<PracticeSession>(sessionPath(userId, profileId, sessionId), signal),
      create: (userId: string, profileId: string, payload: PracticeSessionPayload, signal?: AbortSignal) => request<PracticeSession>(sessionPath(userId, profileId), signal, 'POST', payload),
      complete: (userId: string, profileId: string, sessionId: string, signal?: AbortSignal) => request<PracticeSession>(`${sessionPath(userId, profileId, sessionId)}/complete`, signal, 'POST'),
      abandon: (userId: string, profileId: string, sessionId: string, signal?: AbortSignal) => request<PracticeSession>(`${sessionPath(userId, profileId, sessionId)}/abandon`, signal, 'POST'),
    },
    me: (signal?: AbortSignal) => request<User>('/pilot/me', signal),
    profiles: (userId: string, signal?: AbortSignal) => {
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(userId)) throw new Error('Invalid internal user ID');
      return request<LanguageProfile[]>(`/users/${encodeURIComponent(userId)}/language-profiles`, signal);
    },
  };
}
