export type CEFRLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface User {
  id: string;
  display_name: string;
  created_at: string;
  updated_at: string;
}

export interface Language {
  code: string;
  name: string;
  is_active: boolean;
}

export interface LanguageVariant {
  code: string;
  display_name: string;
  country_code: string | null;
  regional_focus: string | null;
  is_active: boolean;
}

export interface CommunicationRegister {
  code: string;
  display_name: string;
  production_allowed: boolean;
  comprehension_allowed: boolean;
  is_active: boolean;
}

export interface LanguageProfile {
  id: string;
  user_id: string;
  language: Language;
  variant: LanguageVariant;
  cefr_level: CEFRLevel;
  default_production_register: CommunicationRegister;
  comprehension_registers: CommunicationRegister[];
  created_at: string;
  updated_at: string;
}

export interface LanguageProfilePayload {
  language_code: string;
  variant_code: string;
  cefr_level: CEFRLevel;
  default_production_register_code: string;
  comprehension_register_codes: string[];
}
