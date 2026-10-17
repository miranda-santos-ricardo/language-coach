import { useEffect, useState } from "react";
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
  const [voiceDraft, setVoiceDraft] = useState<{ text: string; revision: number; sessionId: string } | null>(null);

  useEffect(() => { setVoiceDraft(null); }, [session.id]);

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

      <button
        type="button"
        className="button button--ghost"
        onClick={onBack}
      >
        Back to languages
      </button>

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