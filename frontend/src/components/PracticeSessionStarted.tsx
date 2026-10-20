import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ConversationPanel } from "./ConversationPanel";
import type {
  LanguageProfile,
  PracticeSession,
} from "../api/types";

interface PracticeSessionStartedProps {
  userId: string;
  profile: LanguageProfile;
  session: PracticeSession;
  onBack: () => void;
}

import { VoiceRecorder } from "./VoiceRecorder";

function trainingModeLabel(
  mode: PracticeSession["training_mode"],
): string {
  switch (mode) {
    case "conversation":
      return "Conversation";

    case "professional":
      return "Professional";

    case "free_talk":
      return "Free Talk";

    case "scenario":
      return "Scenario";
  }
}

export function PracticeSessionStarted({
  userId,
  profile,
  session,
  onBack,
}: PracticeSessionStartedProps) {
  const [confirmCompletion, setConfirmCompletion] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [completionError, setCompletionError] = useState<string | null>(null);
  const [voiceDraft, setVoiceDraft] = useState<{ text: string; revision: number; sessionId: string } | null>(null);

  useEffect(() => {
    setVoiceDraft(null);
    setConfirmCompletion(false);
    setCompleting(false);
    setCompletionError(null);
  }, [session.id]);

  async function completeSession() {
    if (completing || !confirmCompletion) return;
    setCompleting(true);
    setCompletionError(null);
    try {
      const completed = await api.completePracticeSession(userId, profile.id, session.id);
      if (completed.id !== session.id || completed.status !== "completed") {
        throw new Error("The server did not confirm session completion.");
      }
      onBack();
    } catch (reason) {
      setCompletionError(reason instanceof Error ? reason.message : "Unable to complete session.");
    } finally {
      setCompleting(false);
    }
  }

  return (
    <section
      className="panel"
      aria-labelledby="active-session-title"
    >
      <p className="eyebrow">Session started</p>

      <h2 id="active-session-title">
        {profile.variant.display_name}
      </h2>

      <div className="profile-card__facts">
        <span className="badge">
          {trainingModeLabel(session.training_mode)}
        </span>

        <span className="badge badge--accent">
          CEFR {session.effective_cefr}
        </span>
      </div>

      <p className="muted">
        Your practice context is active and ready for the
        conversation layer.
      </p>

      <div className="form-actions" aria-label="Practice session actions">
        <button
          type="button"
          className="button button--ghost"
          onClick={onBack}
          disabled={completing}
        >
          Leave &amp; Resume Later
        </button>
        <button
          type="button"
          className="button button--primary"
          onClick={() => { setConfirmCompletion(true); setCompletionError(null); }}
          disabled={completing || confirmCompletion}
        >
          Complete Session
        </button>
      </div>

      {completionError && <p role="alert" className="alert alert--error">{completionError}</p>}

      {confirmCompletion && (
        <div className="panel" role="group" aria-label="Confirm session completion">
          <p>Complete this session? Your conversation history and feedback will remain available, but you cannot add new turns.</p>
          <div className="form-actions">
            <button type="button" className="button button--ghost" disabled={completing}
              onClick={() => { setConfirmCompletion(false); setCompletionError(null); }}>
              Cancel
            </button>
            <button type="button" className="button button--primary" disabled={completing}
              onClick={() => void completeSession()}>
              {completing ? "Completing…" : "Confirm completion"}
            </button>
          </div>
        </div>
      )}

      <ConversationPanel userId={userId} profileId={profile.id} sessionId={session.id} voiceDraft={voiceDraft?.sessionId === session.id ? voiceDraft : null} />

      <VoiceRecorder
        userId={userId}
        profileId={profile.id}
        practiceSessionId={session.id}
        onUseTranscript={text => setVoiceDraft(previous => ({ text, sessionId: session.id, revision: (previous?.revision ?? 0) + 1 }))}
      />
    </section>
  );
}