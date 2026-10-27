import PilotSessions from './PilotSessions';
import { useEffect, useState } from 'react';
import { beginLogin, clearLoginTransaction, completeLogin, isValidSession } from './oidc';
import type { AuthTokens, OidcConfig } from './oidc';
import { createPilotApi, PilotApiError } from './pilotApi';
import type { User, LanguageProfile } from '../api/types';

function loadConfig(): OidcConfig | null {
  if (import.meta.env.VITE_PILOT_OIDC_ENABLED !== 'true') return null;
  return { issuer:import.meta.env.VITE_OIDC_ISSUER ?? '',clientId:import.meta.env.VITE_OIDC_CLIENT_ID ?? '',redirectUri:import.meta.env.VITE_OIDC_REDIRECT_URI ?? '',authorizationEndpoint:import.meta.env.VITE_OIDC_AUTHORIZATION_ENDPOINT ?? '',tokenEndpoint:import.meta.env.VITE_OIDC_TOKEN_ENDPOINT ?? '',scope:'openid learner:access' };
}
export default function PilotAuthApp() {
  const [tokens,setTokens]=useState<AuthTokens|null>(null);
  const [me,setMe]=useState<User|null>(null);
  const [profiles,setProfiles]=useState<LanguageProfile[]>([]);
  const [error,setError]=useState<string|null>(null);
  const [pending,setPending]=useState(false);
  const config=loadConfig();
  useEffect(()=>{
    if (!config || !location.search.includes('code=') && !location.search.includes('error=')) return;
    let active=true;
    setPending(true);
    void completeLogin(config,location.href).then(value=>{if(active)setTokens(value);}).catch(reason=>{if(active)setError(reason instanceof Error?reason.message:'Authentication failed');}).finally(()=>{
      history.replaceState(null,'',location.pathname); // remove authorization code from URL
      if(active)setPending(false);
    });
    return ()=>{active=false;};
  },[]); // callback processed once, not repeated on state updates
  useEffect(() => {
    if (!tokens || !isValidSession(tokens)) return;
    const controller = new AbortController();
    setPending(true);
    setMe(null); setProfiles([]);
    const base = import.meta.env.VITE_PILOT_API_BASE_URL ?? '';
    try {
      const api = createPilotApi(base, tokens);
      void api.me(controller.signal).then(async user => {
        const result = await api.profiles(user.id, controller.signal);
        if (!controller.signal.aborted) { setMe(user); setProfiles(result); }
      }).catch(reason => {
        if (controller.signal.aborted) return;
        if (reason instanceof PilotApiError && reason.status === 401) setTokens(null);
        setError(reason instanceof Error ? reason.message : 'Pilot API unavailable');
      }).finally(() => { if (!controller.signal.aborted) setPending(false); });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Invalid pilot API configuration');
      setPending(false);
    }
    return () => controller.abort();
  }, [tokens]);
  async function login() {
    if(!config)return;
    setError(null);
    try {location.assign(await beginLogin(config));} catch(reason){setError(reason instanceof Error?reason.message:'Unable to begin login');}
  }
  function logout() {setTokens(null);setMe(null);setProfiles([]);clearLoginTransaction();setError(null);}
  if (!config) return <main><h1>Pilot authentication disabled</h1></main>;
  return <main className="app-shell"><h1>Language Coach — Controlled Pilot</h1>
    {error && <p role="alert">{error}</p>}
    {pending ? <p>Completing sign-in…</p> : isValidSession(tokens) ? <><p>Authenticated learner: {me?.display_name ?? "Loading account…"}</p><h2>My language profiles</h2>{me && (profiles.length ? <ul>{profiles.map(profile => <li key={profile.id}>{profile.language.name} — {profile.cefr_level}</li>)}</ul> : <p>No language profiles yet.</p>)}{me && tokens && <PilotSessions baseUrl={import.meta.env.VITE_PILOT_API_BASE_URL ?? ''} tokens={tokens} userId={me.id} profiles={profiles} onUnauthorized={logout} />}<button onClick={logout}>Log out of this device</button></> : <><p>Sign in to the controlled pilot. The regular practice interface is deliberately unavailable here.</p><button onClick={()=>void login()}>Sign in with identity provider</button></>}
  </main>;
}
