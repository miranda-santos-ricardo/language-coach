import { describe, expect, it, vi } from 'vitest';
import { createPilotApi, PilotApiError } from '../auth/pilotApi';
const user = '9f2b114e-74e3-4eac-8057-ccc451169d29';
const profile = 'a82517c7-7ec4-4e46-9a9c-c10a0dc38955';
const session = 'b82517c7-7ec4-4e46-9a9c-c10a0dc38955';
const tokens = { accessToken: 'test-token', expiresAt: Date.now() + 300000 };
function fakeFetch() {
  return vi.fn(async (_url: string, _init: RequestInit) => ({ ok: true, json: async () => ([]) })) as unknown as typeof fetch;
}
describe('pilot authenticated session lifecycle API', () => {
  it('uses authenticated GET to list sessions only in the selected profile', async () => {
    const fetcher = fakeFetch();
    await createPilotApi('https://api.example', tokens, fetcher).sessions.list(user, profile);
    expect(fetcher).toHaveBeenCalledWith(`https://api.example/users/${user}/language-profiles/${profile}/sessions`,
      expect.objectContaining({ method: 'GET', credentials: 'omit', redirect: 'error', cache: 'no-store', headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) }));
  });
  it('posts the existing session creation schema without any client-derived owner field', async () => {
    const fetcher = fakeFetch();
    await createPilotApi('https://api.example', tokens, fetcher).sessions.create(user, profile, { training_mode: 'conversation', register: 'neutral' });
    const init = (fetcher as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ training_mode: 'conversation', register: 'neutral' });
    expect(init.headers).toMatchObject({ 'Content-Type': 'application/json' });
  });
  it.each(['get', 'complete', 'abandon'] as const)('handles %s without changing session owner', async method => {
    const fetcher = fakeFetch();
    const api = createPilotApi('https://api.example', tokens, fetcher);
    await api.sessions[method](user, profile, session);
    const suffix = method === 'get' ? '' : `/${method}`;
    expect(fetcher).toHaveBeenCalledWith(`https://api.example/users/${user}/language-profiles/${profile}/sessions/${session}${suffix}`, expect.objectContaining({ method: method === 'get' ? 'GET' : 'POST' }));
  });
  it('rejects malformed UUIDs without making HTTP calls', () => {
    const fetcher = fakeFetch();
    expect(() => createPilotApi('https://api.example', tokens, fetcher).sessions.list(user, '../profiles')).toThrow('Invalid internal resource ID');
    expect(() => createPilotApi('https://api.example', tokens, fetcher).sessions.get(user, profile, '../sessions')).toThrow('Invalid internal resource ID');
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('does not send requests after expiration', async () => {
    const fetcher = fakeFetch();
    await expect(createPilotApi('https://api.example', { ...tokens, expiresAt: 0 }, fetcher).sessions.list(user, profile)).rejects.toMatchObject({ status: 401 });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it.each([401, 403, 404, 409, 503])('returns safe API error for HTTP %s', async status => {
    const fetcher = vi.fn(async () => ({ ok: false, status })) as unknown as typeof fetch;
    await expect(createPilotApi('https://api.example', tokens, fetcher).sessions.complete(user, profile, session)).rejects.toMatchObject({ status });
    expect(new PilotApiError(status).message).not.toContain('test-token');
  });
});
