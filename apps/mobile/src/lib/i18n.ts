/**
 * Langue de l'application : celle du téléphone, si elle est prise en charge
 * (français par défaut). Tous les textes visibles passent par `t` (ADR 013).
 */
import * as Localization from "expo-localization";

import closureEn from "../i18n/en/closure.json";
import en from "../i18n/en/ui.json";
import closureFr from "../i18n/fr/closure.json";
import fr from "../i18n/fr/ui.json";
import { type Catalog, type Locale, createTranslator, localeFromTag } from "../i18n/translator";

// `Intl` seul ne reflète pas la langue réglée dans les paramètres du
// téléphone (le moteur JS Hermes renvoie souvent "en-US" par défaut, quel
// que soit le réglage système) : il faut passer par expo-localization.
function deviceLocale(): Locale {
  try {
    return localeFromTag(Localization.getLocales()[0]?.languageTag);
  } catch {
    return "fr";
  }
}

export const locale: Locale = deviceLocale();
// Libellés de clôture sous « closure.* » : disponibles hors ligne.
export const { t } = createTranslator(
  {
    fr: { ...(fr as Catalog), closure: closureFr as Catalog },
    en: { ...(en as Catalog), closure: closureEn as Catalog },
  },
  locale,
);
