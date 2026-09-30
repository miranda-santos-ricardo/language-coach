import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import type {
  CEFRLevel,
  CommunicationRegister,
  LanguageProfile,
  PracticeSession,
  TrainingMode,
} from "../api/types";

interface PracticeSessionFormProps {
  userId: string;
  profile: LanguageProfile;
  onStarted: (session: PracticeSession) => void;
  onCancel: () => void;
}

const cefrLevels: CEFRLevel[] = [
  "A1",
  "A2",
  "B1",
  "B2",
  "C1",
  "C2",
];

function nextCefrLevel(current: CEFRLevel): CEFRLevel | null {
  const index = cefrLevels.indexOf(current);

  if (index < 0 || index === cefrLevels.length - 1) {
    return null;
  }

  return cefrLevels[index + 1];
}

export function PracticeSessionForm({
  userId,
  profile,
  onStarted,
  onCancel,
}: PracticeSessionFormProps) {
  const [trainingMode, setTrainingMode] =
    useState<TrainingMode>("conversation");

  const [registerCode, setRegisterCode] = useState(
    profile.default_production_register.code,
  );

  const [targetCefr, setTargetCefr] =
    useState<CEFRLevel | null>(null);

  const [registers, setRegisters] =
    useState<CommunicationRegister[]>([]);

  const [loadingRegisters, setLoadingRegisters] =
    useState(true);

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const challengeLevel = useMemo(
    () => nextCefrLevel(profile.cefr_level),
    [profile.cefr_level],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadRegisters() {
      setLoadingRegisters(true);
      setError(null);

      try {
        const rows = await api.listRegisters();

        if (!cancelled) {
          setRegisters(
            rows.filter(
              (register) =>
                register.is_active &&
                register.production_allowed,
            ),
          );
        }
      } catch (reason) {
        if (!cancelled) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to load communication registers",
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingRegisters(false);
        }
      }
    }

    void loadRegisters();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setSubmitting(true);
    setError(null);

    try {
      const session = await api.createPracticeSession(
        userId,
        profile.id,
        {
          training_mode: trainingMode,
          register: registerCode,
          target_cefr: targetCefr,
        },
      );

      onStarted(session);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to start practice session",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className="panel"
      aria-labelledby="practice-session-title"
    >
      <div className="panel__header">
        <div>
          <p className="eyebrow">Start practice</p>

          <h2 id="practice-session-title">
            {profile.variant.display_name}
          </h2>

          <p className="muted">
            Choose what you want to practice today.
          </p>
        </div>
      </div>

      {error && (
        <div className="alert alert--error">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Mode</legend>

          <label>
            <input
              type="radio"
              name="training-mode"
              value="conversation"
              checked={trainingMode === "conversation"}
              onChange={() =>
                setTrainingMode("conversation")
              }
            />
            Conversation
          </label>

          <label>
            <input
              type="radio"
              name="training-mode"
              value="professional"
              checked={trainingMode === "professional"}
              onChange={() =>
                setTrainingMode("professional")
              }
            />
            Professional
          </label>

          <label>
            <input
              type="radio"
              name="training-mode"
              value="free_talk"
              checked={trainingMode === "free_talk"}
              onChange={() =>
                setTrainingMode("free_talk")
              }
            />
            Free Talk
          </label>
        </fieldset>

        <fieldset>
          <legend>Register</legend>

          {loadingRegisters ? (
            <p className="muted">
              Loading communication registers…
            </p>
          ) : (
            registers.map((register) => (
              <label key={register.code}>
                <input
                  type="radio"
                  name="communication-register"
                  value={register.code}
                  checked={registerCode === register.code}
                  onChange={() =>
                    setRegisterCode(register.code)
                  }
                />

                {register.display_name}
              </label>
            ))
          )}
        </fieldset>

        <fieldset>
          <legend>Difficulty</legend>

          <label>
            <input
              type="radio"
              name="difficulty"
              checked={targetCefr === null}
              onChange={() => setTargetCefr(null)}
            />

            Use my level — {profile.cefr_level}
          </label>

          {challengeLevel && (
            <label>
              <input
                type="radio"
                name="difficulty"
                checked={targetCefr === challengeLevel}
                onChange={() =>
                  setTargetCefr(challengeLevel)
                }
              />

              Challenge me — {challengeLevel}
            </label>
          )}
        </fieldset>

        <div className="form-actions">
          <button
            type="button"
            className="button button--ghost"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </button>

          <button
            type="submit"
            className="button button--primary"
            disabled={
              submitting ||
              loadingRegisters ||
              !registerCode
            }
          >
            {submitting
              ? "Starting…"
              : "Start practice"}
          </button>
        </div>
      </form>
    </section>
  );
}