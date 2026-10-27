import PilotConversation from './PilotConversation';
import { useEffect, useState } from 'react';
import type { LanguageProfile, PracticeSession, PracticeSessionPayload } from '../api/types';
import type { AuthTokens } from './oidc';
import { createPilotApi, PilotApiError } from './pilotApi';

type Props = { baseUrl: string; tokens: AuthTokens; userId: string; profiles: LanguageProfile[]; onUnauthorized: () => void };

export default function PilotSessions({ baseUrl, tokens, userId, profiles, onUnauthorized }: Props) {
  const [profileId, setProfileId] = useState(profiles[0]?.id ?? '');
  const [sessions, setSessions] = useState<PracticeSession[]>([]);
  const [chosen, setChosen] = useState<PracticeSession | null>(null);
  const [mode, setMode] = useState<PracticeSessionPayload['training_mode']>('conversation');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const profile = profiles.find(p => p.id === profileId);

  useEffect(() => {
    if (!profiles.some(p => p.id === profileId)) setProfileId(profiles[0]?.id ?? '');
  }, [profiles, profileId]);

  useEffect(() => {
    setSessions([]); setChosen(null); setError(null);
    if (!profileId) return;
    const controller = new AbortController();
    try {
      const api = createPilotApi(baseUrl, tokens);
      setBusy(true);
      void api.sessions.list(userId, profileId, controller.signal).then(value => {
        if (!controller.signal.aborted) setSessions(value);
      }).catch(e => { if (!controller.signal.aborted) fail(e); })
        .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    } catch (e) { fail(e); setBusy(false); }
    return () => controller.abort();
  }, [baseUrl, tokens, userId, profileId]);

  function fail(e: unknown) {
    if (e instanceof PilotApiError && e.status === 401) onUnauthorized();
    setError(e instanceof Error ? e.message : 'Session operation failed');
  }
  async function act(action: 'create' | 'complete' | 'abandon' | 'resume', session?: PracticeSession) {
    if (!profileId || busy) return;
    setBusy(true); setError(null);
    try {
      const api = createPilotApi(baseUrl, tokens);
      let value: PracticeSession;
      if (action === 'create') {
        if (!profile) throw new Error('Select a language profile');
        value = await api.sessions.create(userId, profileId, {
          training_mode: mode,
          register: profile.default_production_register.code,
        });
      } else {
        if (!session) throw new Error('Select a practice session');
        value = action === 'resume' ? await api.sessions.get(userId, profileId, session.id)
          : action === 'complete' ? await api.sessions.complete(userId, profileId, session.id)
            : await api.sessions.abandon(userId, profileId, session.id);
      }
      const updated = await api.sessions.list(userId, profileId);
      setSessions(updated);
      setChosen(value.status === 'active' ? value : null);
    } catch (e) { fail(e); }
    finally { setBusy(false); }
  }
  return <section aria-label="Authenticated practice sessions">
    <h2>My practice sessions</h2>
    {error && <p role="alert">{error}</p>}
    <label htmlFor="pilot-profile">Language profile</label>
    <select id="pilot-profile" value={profileId} onChange={e => setProfileId(e.target.value)} disabled={busy}>
      {profiles.map(p => <option key={p.id} value={p.id}>{p.language.name} — {p.cefr_level}</option>)}
    </select>
    <label htmlFor="pilot-mode">Practice mode</label>
    <select id="pilot-mode" value={mode} onChange={e => setMode(e.target.value as PracticeSessionPayload['training_mode'])} disabled={busy}>
      <option value="conversation">Conversation</option><option value="professional">Professional</option>
    </select>
    <button type="button" disabled={!profile || busy} onClick={() => void act('create')}>Create practice session</button>
    {busy && <p>Loading sessions…</p>}
    {chosen && <p role="status">Selected session: {chosen.id} ({chosen.status}). Voice is not yet available.</p>}
    {chosen && chosen.status === 'active' && <PilotConversation key={chosen.id} baseUrl={baseUrl} tokens={tokens} userId={userId} profileId={profileId} sessionId={chosen.id} onUnauthorized={onUnauthorized} />}
    <ul>{sessions.map(s => <li key={s.id}>
      {s.training_mode} — {s.status} — {new Date(s.started_at).toLocaleString()}{' '}
      {s.status === 'active' && <>
        <button type="button" disabled={busy} onClick={() => void act('resume', s)}>Resume</button>{' '}
        <button type="button" disabled={busy} onClick={() => void act('complete', s)}>Complete</button>{' '}
        <button type="button" disabled={busy} onClick={() => void act('abandon', s)}>Abandon</button>
      </>}
    </li>)}</ul>
  </section>;
}
