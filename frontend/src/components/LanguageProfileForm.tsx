import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import { api } from "../api/client";
import type {
  CEFRLevel,
  CommunicationRegister,
  Language,
  LanguageProfile,
  LanguageProfilePayload,
  LanguageVariant,
} from "../api/types";

const CEFR_LEVELS: CEFRLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

interface LanguageProfileFormProps {
  userId: string;
  profile?: LanguageProfile;
  onSaved: (profile: LanguageProfile) => void;
  onCancel: () => void;
}

export function LanguageProfileForm({
  userId,
  profile,
  onSaved,
  onCancel,
}: LanguageProfileFormProps) {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [variants, setVariants] = useState<LanguageVariant[]>([]);
  const [registers, setRegisters] = useState<CommunicationRegister[]>([]);
  const [languageCode, setLanguageCode] = useState(profile?.language.code ?? "");
  const [variantCode, setVariantCode] = useState(profile?.variant.code ?? "");
  const [cefrLevel, setCefrLevel] = useState<CEFRLevel>(profile?.cefr_level ?? "A1");
  const [productionRegister, setProductionRegister] = useState(
    profile?.default_production_register.code ?? "",
  );
  const [comprehensionRegisters, setComprehensionRegisters] = useState<string[]>(
    profile?.comprehension_registers.map((item) => item.code) ?? [],
  );
  const [loadingReferenceData, setLoadingReferenceData] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const productionOptions = useMemo(
    () => registers.filter((register) => register.production_allowed),
    [registers],
  );
  const comprehensionOptions = useMemo(
    () => registers.filter((register) => register.comprehension_allowed),
    [registers],
  );

  useEffect(() => {
    let cancelled = false;
    async function loadReferenceData() {
      setLoadingReferenceData(true);
      try {
        const [languageRows, registerRows] = await Promise.all([
          api.listLanguages(),
          api.listRegisters(),
        ]);
        if (cancelled) return;
        setLanguages(languageRows);
        setRegisters(registerRows);

        setLanguageCode(profile?.language.code ?? "");
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Unable to load reference data");
        }
      } finally {
        if (!cancelled) setLoadingReferenceData(false);
      }
    }
    void loadReferenceData();
    return () => {
      cancelled = true;
    };
  }, [profile]);

  useEffect(() => {
    if (!languageCode) {
      setVariants([]);
      setVariantCode("");
      return;
    }

    let cancelled = false;
    async function loadVariants() {
      try {
        const rows = await api.listVariants(languageCode);
        if (cancelled) return;
        setVariants(rows);
        if (profile?.language.code === languageCode) {
          setVariantCode(profile.variant.code);
        } else {
          setVariantCode(rows[0]?.code ?? "");
        }
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Unable to load language variants");
        }
      }
    }
    void loadVariants();
    return () => {
      cancelled = true;
    };
  }, [languageCode, profile]);

  function toggleComprehension(code: string) {
    setComprehensionRegisters((current) =>
      current.includes(code)
        ? current.filter((item) => item !== code)
        : [...current, code],
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!languageCode || !variantCode || !productionRegister) {
      setError("Choose a language, variant, and default speaking style.");
      return;
    }

    const payload: LanguageProfilePayload = {
      language_code: languageCode,
      variant_code: variantCode,
      cefr_level: cefrLevel,
      default_production_register_code: productionRegister,
      comprehension_register_codes: comprehensionRegisters,
    };

    setSaving(true);
    try {
      const saved = profile
        ? await api.updateProfile(userId, profile.id, payload)
        : await api.createProfile(userId, payload);
      onSaved(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save language profile");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="profile-form-title">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Language profile</p>
          <h2 id="profile-form-title">{profile ? "Edit language profile" : "Add language profile"}</h2>
        </div>
        <button type="button" className="button button--ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      {loadingReferenceData ? (
        <p className="muted">Loading language options…</p>
      ) : (
        <form className="profile-form" onSubmit={handleSubmit}>
          <label>
            Language
            <select
              aria-label="Language"
              value={languageCode}
              onChange={(event: ChangeEvent<HTMLSelectElement>) => setLanguageCode(event.target.value)}
              required
            >
              <option value="" disabled>
                Select a language
              </option>
              {languages.map((language) => (
                <option value={language.code} key={language.code}>
                  {language.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            Variant
            <select
              aria-label="Variant"
              value={variantCode}
              onChange={(event: ChangeEvent<HTMLSelectElement>) => setVariantCode(event.target.value)}
              required
            >
              {variants.map((variant) => (
                <option value={variant.code} key={variant.code}>
                  {variant.display_name}
                </option>
              ))}
            </select>
          </label>

          <label>
            CEFR
            <select
              aria-label="CEFR"
              value={cefrLevel}
              onChange={(event: ChangeEvent<HTMLSelectElement>) => setCefrLevel(event.target.value as CEFRLevel)}
            >
              {CEFR_LEVELS.map((level) => (
                <option value={level} key={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>

          <label>
            Default speaking style
            <select
              aria-label="Default speaking style"
              value={productionRegister}
              onChange={(event: ChangeEvent<HTMLSelectElement>) => setProductionRegister(event.target.value)}
              required
            >
              <option value="" disabled>
                Select a register
              </option>
              {productionOptions.map((register) => (
                <option value={register.code} key={register.code}>
                  {register.display_name}
                </option>
              ))}
            </select>
          </label>

          <fieldset className="register-fieldset">
            <legend>I want to understand</legend>
            <div className="checkbox-grid">
              {comprehensionOptions.map((register) => (
                <label className="checkbox-option" key={register.code}>
                  <input
                    type="checkbox"
                    checked={comprehensionRegisters.includes(register.code)}
                    onChange={() => toggleComprehension(register.code)}
                  />
                  <span>{register.display_name}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="form-actions">
            <button className="button button--primary" type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
