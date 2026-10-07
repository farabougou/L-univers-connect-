/**
 * Langue de la console : celle demandée par le navigateur (Accept-Language),
 * si elle est prise en charge ; français par défaut (ADR 013).
 */
import { headers } from "next/headers";

import enErrors from "@/i18n/en/errors.json";
import en from "@/i18n/en/ui.json";
import frErrors from "@/i18n/fr/errors.json";
import fr from "@/i18n/fr/ui.json";
import {
  type Catalog,
  type Locale,
  type Translator,
  createTranslator,
  negotiateLocale,
} from "@/i18n/translator";

const catalogs = { fr: fr as Catalog, en: en as Catalog };
const errorCatalogs: Record<Locale, { codes: Record<string, string> }> = {
  fr: frErrors,
  en: enErrors,
};

export async function getLocale(): Promise<Locale> {
  return negotiateLocale((await headers()).get("accept-language"));
}

export async function getTranslator(): Promise<Translator> {
  return createTranslator(catalogs, await getLocale());
}

export function translatorFor(locale: Locale): Translator {
  return createTranslator(catalogs, locale);
}

/**
 * Message d'une erreur de l'API à partir de son code stable (le texte n'est
 * jamais transmis dans l'adresse) ; `null` si le code est inconnu.
 */
export function errorMessage(locale: Locale, code: string): string | null {
  const template = errorCatalogs[locale].codes[code];
  return template && !template.includes("{") ? template : null;
}
