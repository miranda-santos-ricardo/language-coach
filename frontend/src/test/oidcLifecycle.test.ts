import { webcrypto } from 'node:crypto';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { beginLogin, completeLogin, clearLoginTransaction, isValidSession, type OidcConfig } from '../auth/oidc';
const config:OidcConfig={issuer:'https://idp.example.test',clientId:'pilot-spa',redirectUri:`${location.origin}/`,authorizationEndpoint:'https://idp.example.test/authorize',tokenEndpoint:'https://idp.example.test/token',scope:'openid learner:access'};
beforeEach(()=>{Object.defineProperty(globalThis, 'crypto', {configurable:true,value:webcrypto});sessionStorage.clear();vi.restoreAllMocks();});
describe('OIDC PKCE lifecycle',()=>{
  it('starts authorization code + S256 with state nonce and no implicit response',async()=>{
    const url=new URL(await beginLogin(config));
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(url.searchParams.get('code_challenge')?.length).toBe(43);
    expect(url.searchParams.get('nonce')).toBeTruthy();
    expect(url.searchParams.get('state')).toBeTruthy();
  });
  it('exchanges code with verifier only once and retains access token in memory',async()=>{
    const url=new URL(await beginLogin(config));
    const state=url.searchParams.get('state');
    const fetcher=vi.fn(async (_url:string,options:RequestInit)=>{
      expect(options.method).toBe('POST');
      expect(String(options.body)).toContain('code_verifier=');
      return {ok:true,json:async()=>({access_token:'signed-token',token_type:'Bearer',expires_in:180})};
    }) as unknown as typeof fetch;
    const callback=`${location.origin}/?code=abc&state=${state}`;
    expect((await completeLogin(config,callback,fetcher)).accessToken).toBe('signed-token');
    expect(sessionStorage.length).toBe(0);
    await expect(completeLogin(config,callback,fetcher)).rejects.toThrow('missing');
  });
  it('rejects CSRF mismatched state without exchanging token',async()=>{
    await beginLogin(config);
    const fetcher=vi.fn() as unknown as typeof fetch;
    await expect(completeLogin(config,`${location.origin}/?code=abc&state=wrong`,fetcher)).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('rejects OAuth error callback',async()=>{
    await beginLogin(config);
    await expect(completeLogin(config,`${location.origin}/?error=access_denied`)).rejects.toThrow();
  });
  it('rejects duplicate code parameters',async()=>{
    const url=new URL(await beginLogin(config));
    await expect(completeLogin(config,`${location.origin}/?code=a&code=b&state=${url.searchParams.get('state')}`)).rejects.toThrow();
  });
  it('requires trusted issuer origin and HTTPS',async()=>{
    await expect(beginLogin({...config, tokenEndpoint:'https://evil.example/token'})).rejects.toThrow();
    await expect(beginLogin({...config,issuer:'http://idp.example.test'})).rejects.toThrow();
  });
  it('clears pending transaction and rejects expired sessions',async()=>{
    await beginLogin(config);clearLoginTransaction();expect(sessionStorage.length).toBe(0);
    expect(isValidSession({accessToken:'abc',expiresAt:Date.now()-1})).toBe(false);
  });
});
