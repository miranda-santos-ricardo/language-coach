import { describe, expect, it, vi } from 'vitest';
import { createPilotApi, PilotApiError } from '../auth/pilotApi';
const user = '9f2b114e-74e3-4eac-8057-ccc451169d29';
const profile = 'a82517c7-7ec4-4e46-9a9c-c10a0dc38955';
const session = 'b82517c7-7ec4-4e46-9a9c-c10a0dc38955';
const turn = 'c82517c7-7ec4-4e46-9a9c-c10a0dc38955';
const tokens = { accessToken: 'test-token', expiresAt: Date.now() + 300000 };
const fake = () => vi.fn(async () => ({ok:true, json: async () => ({items:[],limit:50,offset:0})})) as unknown as typeof fetch;
describe('authenticated pilot text conversation API', () => {
  it('reads only under the guarded owner/profile/session route', async () => {
    const fetcher = fake();
    const api = createPilotApi('https://api.example', tokens, fetcher);
    await api.turns.list(user,profile,session);
    expect(fetcher).toHaveBeenCalledWith(`https://api.example/users/${user}/language-profiles/${profile}/sessions/${session}/turns?limit=50&offset=0`,
      expect.objectContaining({method:'GET', credentials:'omit', headers:expect.objectContaining({Authorization:'Bearer test-token'})}));
    await api.turns.get(user,profile,session,turn);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it('submits one text turn with existing idempotency contract', async () => {
    const fetcher = fake();
    const api = createPilotApi('https://api.example', tokens, fetcher);
    await api.turns.submit(user,profile,session,{text:'Bonjour',input_modality:'text',client_request_id:turn});
    const init = (fetcher as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({text:'Bonjour',input_modality:'text',client_request_id:turn});
  });
  it('rejects malformed IDs, invalid pagination and voice payload without network', () => {
    const fetcher = fake(); const api = createPilotApi('https://api.example',tokens,fetcher);
    expect(() => api.turns.list(user,profile,'../escape')).toThrow();
    expect(() => api.turns.get(user,profile,session,'../escape')).toThrow();
    expect(() => api.turns.list(user,profile,session,101)).toThrow();
    expect(() => api.turns.submit(user,profile,session,{text:'x',input_modality:'voice',client_request_id:turn})).toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('fails closed on expired bearer and propagates 404 access isolation', async () => {
    const fetcher = fake();
    await expect(createPilotApi('https://api.example',{...tokens,expiresAt:0},fetcher).turns.list(user,profile,session)).rejects.toMatchObject({status:401});
    expect(fetcher).not.toHaveBeenCalled();
    const denied = vi.fn(async () => ({ok:false,status:404})) as unknown as typeof fetch;
    await expect(createPilotApi('https://api.example',tokens,denied).turns.list(user,profile,session)).rejects.toBeInstanceOf(PilotApiError);
  });
});
