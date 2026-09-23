/**
 * Langue de l'application : celle du téléphone, si elle est prise en charge
 * (français par défaut). Tous les textes visibles passent par `t` (ADR 013).
 */
import en from "../i18n/en/ui.json";
import fr from "../i18n/fr/ui.json";
import { type Catalog, type Locale, createTranslator, localeFromTag } from "../i18n/translator";

function deviceLocale(): Locale {
  try {
    return localeFromTag(Intl.DateTimeFormat().resolvedOptions().locale);
  } catch {
    return "fr";
  }
}

export const locale: Locale = deviceLocale();
export const { t } = createTranslator({ fr: fr as Catalog, en: en as Catalog }, locale);
