import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { PracticeSession } from "../api/types";

interface Props {
  userId: string;
  profileId: string;
  onResume: (session: PracticeSession) => void;
}

export function ResumePracticeSessions({ userId, profileId, onResume }: Props) {
  const generation = useRef(0);
  const [sessions, setSessions] = useState<PracticeSession[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resumingId, setResumingId] = useState<string | null>(null);

  useEffect(() => {
    // Clear results when a different profile is selected.
    generation.current += 1;
    setSessions([]);
    setExpanded(false);
    setError(null);
    setResumingId(null);
  }, [userId, profileId]);

  async function openSessions() {
    if (loading || resumingId) return;
    const token = ++generation.current;
    setExpanded(true);
    setLoading(true);
    setError(null);
    try {
      const rows = await api.listPracticeSessions(userId, profileId);
      if (token !== generation.current) return;
      setSessions(rows.filter(s => s.status === "active" && s.language_profile_id === profileId)
        .sort((a, b) => b.started_at.localeCompare(a.started_at)));
    } catch (reason) {
      if (token === generation.current) setError(reason instanceof Error ? reason.message : "Could not load sessions");
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }

  async function resume(sessionId: string) {
    if (resumingId) return;
    const token = generation.current;
    setResumingId(sessionId);
    setError(null);
    try {
      // Revalidate status and ownership at the server immediately before resuming.
      const session = await api.getPracticeSession(userId, profileId, sessionId);
      if (token !== generation.current) return;
      if (session.status !== "active" || session.language_profile_id !== profileId) {
        setSessions(rows => rows.filter(s => s.id !== sessionId));
        setError("This practice session is no longer active.");
        return;
      }
      onResume(session);
    } catch (reason) {
      if (token === generation.current) setError(reason instanceof Error ? reason.message : "Could not resume session");
    } finally {
      if (token === generation.current) setResumingId(null);
    }
  }

  return <section aria-label="Existing practice sessions">
    <button type="button" disabled={loading || resumingId !== null} onClick={() => void openSessions()}>
      {loading ? "Loading sessions…" : expanded ? "Refresh active sessions" : "Find active sessions"}
    </button>
    {error && <p role="alert">{error}</p>}
    {expanded && !loading && !error && sessions.length === 0 && <p>No active sessions for this profile.</p>}
    {expanded && sessions.length > 0 && <ul aria-label="Active practice sessions">
      {sessions.map(session => <li key={session.id}>
        <span>{session.training_mode} · CEFR {session.effective_cefr} · {new Date(session.started_at).toLocaleDateString()}</span>{" "}
        <button type="button" disabled={resumingId !== null} onClick={() => void resume(session.id)}>
          {resumingId === session.id ? "Resuming…" : "Resume session"}
        </button>
      </li>)}
    </ul>}
  </section>;
}
