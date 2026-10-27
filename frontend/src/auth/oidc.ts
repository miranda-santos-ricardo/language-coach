/** Experimental isolated OIDC SPA lifecycle. No refresh tokens and no local token persistence. */
export type OidcConfig = { issuer: string; clientId: string; redirectUri: string; authorizationEndpoint: string; tokenEndpoint: string; scope: string };
export type AuthTokens = { accessToken: string; expiresAt: number };
const TRANSACTION_KEY = 'language-coach:oidc:transaction:v1';
type Tx = { state: string; nonce: string; verifier: string; startedAt: number };
const URL_SAFE = /^[a-zA-Z0-9._~-]+$/;
const encoder = new TextEncoder();
export function validateConfig(config: OidcConfig): void {
  const urls = [config.issuer, config.redirectUri, config.authorizationEndpoint, config.tokenEndpoint];
  if (!config.clientId || !config.scope || !urls.every(Boolean)) throw new Error('Invalid OIDC config');
  for (const url of urls) {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && parsed.hostname === 'localhost')) throw new Error('OIDC requires HTTPS');
    if (parsed.username || parsed.password || parsed.hash) throw new Error('Invalid OIDC URL');
  }
  if (new URL(config.authorizationEndpoint).origin !== new URL(config.issuer).origin || new URL(config.tokenEndpoint).origin !== new URL(config.issuer).origin) throw new Error('OIDC endpoints must share trusted origin');
  if (new URL(config.redirectUri).origin !== location.origin) throw new Error('Redirect URI must belong to this app');
  if (!config.scope.split(' ').includes('openid')) throw new Error('openid scope required');
}
function randomUrlSafe(bytes = 32): string {
  const data = new Uint8Array(bytes);
  crypto.getRandomValues(data);
  return Array.from(data, x => x.toString(16).padStart(2, '0')).join('');
}
function base64url(data: ArrayBuffer): string {
  const bytes = new Uint8Array(data);
  let raw = '';
  for (const byte of bytes) raw += String.fromCharCode(byte);
  return btoa(raw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}
export async function beginLogin(config: OidcConfig, storage: Storage = sessionStorage): Promise<string> {
  validateConfig(config);
  const verifier = randomUrlSafe(48);
  const state = randomUrlSafe();
  const nonce = randomUrlSafe();
  const challenge = base64url(await crypto.subtle.digest('SHA-256', encoder.encode(verifier)));
  storage.setItem(TRANSACTION_KEY, JSON.stringify({ state, nonce, verifier, startedAt: Date.now() } satisfies Tx));
  const url = new URL(config.authorizationEndpoint);
  for (const [k,v] of Object.entries({ response_type:'code',client_id:config.clientId,redirect_uri:config.redirectUri,scope:config.scope,state,nonce,code_challenge:challenge,code_challenge_method:'S256' })) url.searchParams.set(k,v);
  return url.toString();
}
export async function completeLogin(config: OidcConfig, callbackUrl: string, fetcher: typeof fetch = fetch, storage: Storage = sessionStorage): Promise<AuthTokens> {
  validateConfig(config);
  const raw = storage.getItem(TRANSACTION_KEY);
  storage.removeItem(TRANSACTION_KEY); // single-use even on error
  if (!raw) throw new Error('Login transaction missing or already used');
  let tx: Tx;
  try { tx=JSON.parse(raw) as Tx; } catch { throw new Error('Invalid login transaction'); }
  if (!tx || typeof tx.state!=='string' || typeof tx.verifier!=='string' || !URL_SAFE.test(tx.verifier) || !Number.isFinite(tx.startedAt) || Date.now()-tx.startedAt>5*60_000 || Date.now()<tx.startedAt-30_000) throw new Error('Expired login transaction');
  const callback=new URL(callbackUrl);
  if (callback.origin!==new URL(config.redirectUri).origin || callback.pathname!==new URL(config.redirectUri).pathname) throw new Error('Callback URI mismatch');
  if (callback.searchParams.has('error')) throw new Error('Identity provider rejected authorization');
  if (callback.searchParams.getAll('state').length!==1 || callback.searchParams.get('state')!==tx.state || callback.searchParams.getAll('code').length!==1 || !callback.searchParams.get('code')) throw new Error('Invalid callback state or code');
  const body=new URLSearchParams({grant_type:'authorization_code',code:callback.searchParams.get('code')!,redirect_uri:config.redirectUri,client_id:config.clientId,code_verifier:tx.verifier});
  const response=await fetcher(config.tokenEndpoint,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body,cache:'no-store',credentials:'omit',redirect:'error'});
  if (!response.ok) throw new Error('Token exchange failed');
  const result=await response.json() as Record<string, unknown>;
  if (typeof result.access_token!=='string' || !result.access_token || result.token_type!=='Bearer' || typeof result.expires_in!=='number' || !Number.isFinite(result.expires_in) || result.expires_in<=0 || result.expires_in>86400) throw new Error('Invalid token response');
  // The access token is not treated as identity in the browser. Backend validates it.
  return {accessToken:result.access_token,expiresAt:Date.now()+result.expires_in*1000};
}
export function clearLoginTransaction(storage: Storage = sessionStorage): void {storage.removeItem(TRANSACTION_KEY);}
export function isValidSession(tokens: AuthTokens | null): boolean {return !!tokens && Date.now()+10_000<tokens.expiresAt;}
