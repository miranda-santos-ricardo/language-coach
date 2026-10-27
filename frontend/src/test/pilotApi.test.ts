import { describe, expect, it, vi } from 'vitest';
import { createPilotApi, PilotApiError } from '../auth/pilotApi';
const tokens = {accessToken:'token-in-memory', expiresAt: Date.now()+300000};
describe('isolated authenticated pilot API', () => {
  it('requires trusted HTTPS configuration', () => {
    expect(() => createPilotApi('http://remote.example', tokens)).toThrow();
    expect(() => createPilotApi('https://user:pass@api.example', tokens)).toThrow();
  });
  it('sends Bearer token only to configured API and never credentials', async () => {
    const fetcher = vi.fn(async (_url:string, init:RequestInit) => {
      expect(init.credentials).toBe('omit');
      expect(init.redirect).toBe('error');
      expect(init.cache).toBe('no-store');
      expect((init.headers as Record<string,string>).Authorization).toBe('Bearer token-in-memory');
      return {ok:true,json:async()=>({id:'first-user'})};
    }) as unknown as typeof fetch;
    await createPilotApi('https://api.example',tokens,fetcher).me();
    expect(fetcher).toHaveBeenCalledWith('https://api.example/pilot/me',expect.any(Object));
  });
  it('refuses expired token before network call', async () => {
    const fetcher=vi.fn() as unknown as typeof fetch;
    await expect(createPilotApi('https://api.example',{...tokens,expiresAt:1},fetcher).me()).rejects.toMatchObject({status:401});
    expect(fetcher).not.toHaveBeenCalled();
  });
  it.each([401,403,404,503])('returns safe status for %i without exposing token',async status=>{
    const fetcher=vi.fn(async()=>({ok:false,status})) as unknown as typeof fetch;
    const request=createPilotApi('https://api.example',tokens,fetcher).me();
    await expect(request).rejects.toBeInstanceOf(PilotApiError);
    await expect(request).rejects.toMatchObject({status});
  });
  it('blocks malformed user IDs before requesting profiles', async()=>{
    const fetcher=vi.fn() as unknown as typeof fetch;
    expect(() => createPilotApi('https://api.example',tokens,fetcher).profiles('../users')).toThrow('Invalid internal user ID');
    expect(fetcher).not.toHaveBeenCalled();
  });
});
