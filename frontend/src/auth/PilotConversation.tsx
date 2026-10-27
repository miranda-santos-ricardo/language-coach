import { useEffect, useState } from 'react';
import type { AuthTokens } from './oidc';
import type { ConversationTurnDetail, ConversationTurnPage } from '../api/conversations';
import { createPilotApi, PilotApiError } from './pilotApi';

type Props = { baseUrl: string; tokens: AuthTokens; userId: string; profileId: string; sessionId: string; onUnauthorized: () => void };

/** Pilot text-only conversation; no voice or experimental assessment activation. */
export default function PilotConversation({ baseUrl, tokens, userId, profileId, sessionId, onUnauthorized }: Props) {
  const [history, setHistory] = useState<ConversationTurnDetail[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setHistory([]); setError(null); setUncertain(false);
    const api = createPilotApi(baseUrl, tokens);
    void api.turns.list(userId, profileId, sessionId, 50, 0, controller.signal)
      .then((page: ConversationTurnPage) => { if (!controller.signal.aborted) setHistory(page.items); })
      .catch(e => { if (!controller.signal.aborted) handleError(e); });
    return () => controller.abort();
  // Intentional: new history fetch on selection or manual refresh; identity remains server-verified.
  }, [baseUrl, tokens, userId, profileId, sessionId, reload]);
  function handleError(e: unknown) {
    if (e instanceof PilotApiError && e.status === 401) onUnauthorized();
    setError(e instanceof PilotApiError ? e.message : 'Unable to load conversation history');
  }
  async function submit() {
    if (busy || uncertain || !text.trim() || text.length > 4000) return;
    setBusy(true); setError(null);
    try {
      const api = createPilotApi(baseUrl, tokens);
      // One ID per attempt, and no automatic retry on an indeterminate HTTP outcome.
      await api.turns.submit(userId, profileId, sessionId, {
        text: text.trim(), input_modality: 'text', client_request_id: crypto.randomUUID(),
      });
      setText(''); setReload(v => v + 1);
    } catch (e) {
      handleError(e);
      // Any failed mutation may have committed; explicit reconciliation before new submission.
      setUncertain(true);
      setError('Submission outcome is uncertain. Review persisted history before sending again.');
    } finally { setBusy(false); }
  }
  return <section aria-label="Authenticated conversation">
    <h3>Text conversation</h3>
    {error && <p role="alert">{error}</p>}
    {uncertain && <p role="status">Do not resubmit the previous message automatically.</p>}
    <button type="button" disabled={busy} onClick={() => { setUncertain(false); setReload(v => v + 1); }}>Refresh history</button>
    <ol>{history.map(turn => <li key={turn.turn_id}>
      <p><strong>You:</strong> {turn.learner_text}</p>
      <p><strong>Coach:</strong> {turn.coach_response}</p>
      <p><strong>Feedback:</strong> {turn.feedback.overall_assessment}</p>
    </li>)}</ol>
    <label htmlFor="pilot-turn-text">Your message</label>
    <textarea id="pilot-turn-text" value={text} onChange={e => setText(e.target.value)} maxLength={4000} disabled={busy || uncertain} />
    <button type="button" onClick={() => void submit()} disabled={busy || uncertain || !text.trim()}>Send text message</button>
  </section>;
}
