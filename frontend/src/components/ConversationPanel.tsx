import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../api/client";
import { conversationsApi } from "../api/conversations";
import type { ConversationContextIds, ConversationTurnDetail, TurnSubmitted } from "../api/conversations";
import { LanguageFeedbackPanel } from "./LanguageFeedbackPanel";

const PAGE_SIZE = 50;
const MAX_TEXT = 4000;
function newRequestId(): string {
  // getRandomValues works on LAN HTTP origins where randomUUID may be unavailable.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
// Keep pagination deterministic even if the server returns overlapping rows.
export function mergeConversationTurns(previous: ConversationTurnDetail[], incoming: ConversationTurnDetail[], replace = false): ConversationTurnDetail[] {
  const byId = new Map<string, ConversationTurnDetail>();
  for (const turn of (replace ? [] : previous)) byId.set(turn.turn_id, turn);
  for (const turn of incoming) byId.set(turn.turn_id, turn);
  return [...byId.values()].sort((a, b) => a.turn_index - b.turn_index || a.turn_id.localeCompare(b.turn_id));
}

function errorText(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 409) return `${reason.message} Please review the session and try again.`;
    if (reason.status === 503 || reason.status === 504 || reason.status === 502) return "AI Coach is temporarily unavailable. Your message was kept; retry when ready.";
    return reason.message;
  }
  return "Unable to contact the AI Coach. Your message was kept; retry when ready.";
}

interface ConversationPanelProps extends ConversationContextIds {
  voiceDraft?: { text: string; revision: number } | null;
}

export function ConversationPanel({ userId, profileId, sessionId, voiceDraft }: ConversationPanelProps) {
  const context = { userId, profileId, sessionId };
  const [draft, setDraft] = useState("");
  const [modality, setModality] = useState<"text" | "voice">("text");
  const [history, setHistory] = useState<ConversationTurnDetail[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<TurnSubmitted | null>(null);
  const pending = useRef<{ text: string; modality: "text" | "voice"; id: string } | null>(null);
  const submittingRef = useRef(false);
  const identity = JSON.stringify([userId, profileId, sessionId]);
  const activeIdentity = useRef(identity);
  activeIdentity.current = identity;
  const historyRequest = useRef(0);
  const historyLoading = useRef(false);

  async function loadHistory(nextOffset: number, replace: boolean) {
    if (historyLoading.current) return;
    historyLoading.current = true;
    const request = ++historyRequest.current;
    const requestIdentity = identity;
    setHistoryBusy(true);
    setHistoryError(null);
    try {
      const page = await conversationsApi.list(context, PAGE_SIZE, nextOffset);
      if (activeIdentity.current !== requestIdentity || request !== historyRequest.current) return;
      setHistory(previous => mergeConversationTurns(previous, page.items, replace));
      // Offset counts server rows rather than unique rows, to avoid skipping pages.
      setOffset(nextOffset + page.items.length);
      setHasMore(page.items.length === PAGE_SIZE);
    } catch (reason) {
      if (activeIdentity.current === requestIdentity && request === historyRequest.current)
        setHistoryError(reason instanceof Error ? reason.message : "Unable to load history");
    } finally {
      if (activeIdentity.current === requestIdentity && request === historyRequest.current) {
        historyLoading.current = false;
        setHistoryBusy(false);
      }
    }
  }

  useEffect(() => {
    // A prior session's pending responses cannot populate this session.
    activeIdentity.current = identity;
    historyLoading.current = false;
    ++historyRequest.current;
    setDraft(""); setModality("text"); setLastResult(null); setSubmitError(null); pending.current = null;
    setHistory([]); setOffset(0); setHasMore(false); setHistoryBusy(false); setHistoryError(null);
    void loadHistory(0, true);
    return () => { ++historyRequest.current; };
  }, [identity]);

  // Moving a transcript into the editor is a separate, explicit user action.
  // A revision token also permits reusing an identical transcription twice.
  useEffect(() => {
    if (!voiceDraft) return;
    // The active request is not overwritten while a submission is in progress.
    if (submittingRef.current) return;
    setDraft(voiceDraft.text);
    setModality("voice");
    setSubmitError(null);
    pending.current = null;
  }, [voiceDraft?.revision, identity]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current || !draft.trim() || draft.length > MAX_TEXT) return;
    submittingRef.current = true;
    setSubmitting(true); setSubmitError(null);
    const submittedIdentity = identity;
    const text = draft.trim();
    const request = pending.current?.text === text && pending.current?.modality === modality ? pending.current : { text, modality, id: newRequestId() };
    pending.current = request;
    try {
      const result = await conversationsApi.submit(context, {
        text, input_modality: modality, client_request_id: request.id,
      });
      if (activeIdentity.current !== submittedIdentity) return;
      pending.current = null;
      setDraft(""); setModality("text"); setLastResult(result);
      await loadHistory(0, true);
    } catch (reason) {
      if (activeIdentity.current === submittedIdentity) setSubmitError(errorText(reason));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  return <section className="conversation-panel" aria-labelledby="conversation-title">
    <h3 id="conversation-title">AI Conversation Coach</h3>
    <p className="muted">Type a message, or move a transcript into the editor to review it before sending.</p>
    {historyBusy && <p role="status">Loading conversation history…</p>}
    {historyError && <div role="alert">{historyError} <button type="button" onClick={() => void loadHistory(0, true)}>Retry history</button></div>}
    <ol className="conversation-history" aria-label="Conversation history">
      {history.map(turn => <li key={turn.turn_id}>
        <p><strong>You:</strong> {turn.learner_text}</p>
        <p><strong>Coach:</strong> {turn.coach_response}</p>
        <LanguageFeedbackPanel feedback={turn.feedback} />
      </li>)}
    </ol>
    {hasMore && <button type="button" disabled={historyBusy} onClick={() => void loadHistory(offset, false)}>Load more turns</button>}
    {lastResult && !history.some(turn => turn.turn_id === lastResult.turn_id) && <div aria-label="Latest coach response">
      <p><strong>Coach:</strong> {lastResult.coach_response}</p>
      <LanguageFeedbackPanel feedback={lastResult.feedback} />
    </div>}
    <form onSubmit={event => void submit(event)}>
      <label htmlFor="coach-draft">Your message</label>
      {modality === "voice" && <p role="status">Voice transcript — review or edit before sending.</p>}
      <textarea id="coach-draft" rows={4} maxLength={MAX_TEXT} value={draft}
        onChange={event => { setDraft(event.target.value); setSubmitError(null); pending.current = null; }}
        disabled={submitting} />
      <button className="button button--primary" type="submit" disabled={submitting || !draft.trim()}>
        {submitting ? "Sending…" : "Send to Coach"}
      </button>
    </form>
    {submitError && <div role="alert">{submitError}</div>}
  </section>;
}
