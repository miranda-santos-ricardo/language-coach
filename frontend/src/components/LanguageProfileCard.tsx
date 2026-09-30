import type { LanguageProfile } from "../api/types";

interface LanguageProfileCardProps {
  profile: LanguageProfile;
  onEdit: (profile: LanguageProfile) => void;
  onStartPractice: (profile: LanguageProfile) => void;
}

function countryFlag(countryCode: string | null): string {
  if (!countryCode || !/^[A-Z]{2}$/.test(countryCode)) return "🌐";
  return String.fromCodePoint(
    ...[...countryCode].map((letter) => 127397 + letter.charCodeAt(0)),
  );
}

export function LanguageProfileCard({ profile, onEdit, onStartPractice }: LanguageProfileCardProps) {
  return (
    <article className="profile-card">
      <div className="profile-card__topline">
        <span className="profile-card__flag" aria-hidden="true">
          {countryFlag(profile.variant.country_code)}
        </span>
        <div>
          <h3>{profile.variant.display_name}</h3>
          <p className="muted">{profile.language.name}</p>
        </div>
        <button
          type="button"
          className="button button--ghost profile-card__edit"
          onClick={() => onEdit(profile)}
        >
          Edit
        </button>
        <button
          type="button"
          className="button button--primary"
          onClick={() => onStartPractice(profile)}
        >
          Start practice
        </button>
      </div>

      <div className="profile-card__facts">
        <span className="badge">CEFR {profile.cefr_level}</span>
        <span className="badge badge--accent">
          {profile.default_production_register.display_name}
        </span>
      </div>

      <div className="profile-card__section">
        <strong>Understand</strong>
        {profile.comprehension_registers.length === 0 ? (
          <span className="muted">No registers selected</span>
        ) : (
          <div className="tag-list">
            {profile.comprehension_registers.map((register) => (
              <span className="tag" key={register.code}>
                {register.display_name}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
