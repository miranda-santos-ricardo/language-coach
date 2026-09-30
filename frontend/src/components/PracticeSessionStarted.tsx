import type {
  LanguageProfile,
  PracticeSession,
} from "../api/types";

interface PracticeSessionStartedProps {
  profile: LanguageProfile;
  session: PracticeSession;
  onBack: () => void;
}

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
  profile,
  session,
  onBack,
}: PracticeSessionStartedProps) {
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
    </section>
  );
}