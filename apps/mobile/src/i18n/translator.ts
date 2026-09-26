/**
 * Traducteur commun au web et au mobile (ADR 013, étape L4).
 *
 * Source unique : ce fichier et les catalogues de `shared/i18n/` sont copiés
 * dans chaque application par `shared/i18n/sync.mjs` ; un test de chaque
 * application échoue si une copie diffère de l'original. Ne pas modifier les
 * copies : modifier ici, puis relancer `npm run i18n:sync`.
 *
 * Aucune dépendance : les règles de pluriel, les dates, les nombres et les
 * fuseaux horaires viennent de `Intl` (données Unicode CLDR), intégré au
 * moteur JavaScript. Messages au format `{nom}` ; un pluriel s'écrit
 * `{ "one": "...", "other": "..." }` et se choisit avec le paramètre `count`.
 */

export type Locale = "fr" | "en";
export const SUPPORTED_LOCALES: readonly Locale[] = ["fr", "en"];
export const DEFAULT_LOCALE: Locale = "fr";

type Plural = { one: string; other: string };
type Message = string | Plural;
export type Catalog = { [key: string]: Message | Catalog };
export type Params = Record<string, string | number | null | undefined>;

function isLocale(value: string): value is Locale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

/** « fr-FR » → « fr » ; langue non prise en charge → français. */
export function localeFromTag(tag: string | null | undefined): Locale {
  const language = (tag ?? "").trim().toLowerCase().split(/[-_]/)[0];
  return isLocale(language) ? language : DEFAULT_LOCALE;
}

/** Même algorithme que l'API : langue préférée de l'en-tête Accept-Language. */
export function negotiateLocale(header: string | null | undefined): Locale {
  if (!header) return DEFAULT_LOCALE;
  let bestLocale: Locale = DEFAULT_LOCALE;
  let bestWeight = 0;
  for (const part of header.split(",")) {
    const [tag, ...parameters] = part.trim().split(";");
    const language = tag.trim().toLowerCase().split("-")[0];
    let weight = 1;
    for (const parameter of parameters) {
      const [name, value] = parameter.trim().split("=");
      if (name?.trim() === "q") {
        const parsed = Number(value);
        weight = Number.isFinite(parsed) ? parsed : 0;
      }
    }
    // À poids égal, la première langue citée l'emporte.
    if (isLocale(language) && weight > bestWeight) {
      bestLocale = language;
      bestWeight = weight;
    }
  }
  return bestLocale;
}

function lookup(catalog: Catalog, key: string): Message | undefined {
  let node: Message | Catalog | undefined = catalog;
  for (const part of key.split(".")) {
    if (node === undefined || typeof node === "string" || isPlural(node)) return undefined;
    node = (node as Catalog)[part];
  }
  if (typeof node === "string" || (node && isPlural(node))) return node as Message;
  return undefined;
}

function isPlural(node: Message | Catalog): node is Plural {
  return typeof node === "object" && typeof node.one === "string" && typeof node.other === "string";
}

export function pluralCategory(locale: Locale, count: number): "one" | "other" {
  try {
    return new Intl.PluralRules(locale).select(count) === "one" ? "one" : "other";
  } catch {
    // Moteur sans Intl.PluralRules : règles CLDR du français et de l'anglais.
    if (locale === "fr") return count >= 0 && count < 2 ? "one" : "other";
    return count === 1 ? "one" : "other";
  }
}

export function formatNumber(locale: Locale, value: number, maximumFractionDigits = 2): string {
  try {
    return new Intl.NumberFormat(locale, { maximumFractionDigits }).format(value);
  } catch {
    return String(value);
  }
}

/**
 * Date et heure dans la langue choisie. Avec `timeZone` (fuseau IANA du
 * site), l'heure est celle du site ; sans, celle de l'appareil.
 */
export function formatDateTime(
  locale: Locale,
  value: string | Date,
  timeZone?: string | null,
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  try {
    return new Intl.DateTimeFormat(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      ...(timeZone ? { timeZone } : {}),
    }).format(date);
  } catch {
    return date.toISOString();
  }
}

export function formatDate(locale: Locale, value: string | Date, timeZone?: string | null): string {
  const date = typeof value === "string" ? new Date(value) : value;
  try {
    return new Intl.DateTimeFormat(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      ...(timeZone ? { timeZone } : {}),
    }).format(date);
  } catch {
    return date.toISOString().slice(0, 10);
  }
}

export type Translator = {
  locale: Locale;
  t: (key: string, params?: Params) => string;
  has: (key: string) => boolean;
};

export function createTranslator(catalogs: Record<Locale, Catalog>, locale: Locale): Translator {
  const catalog = catalogs[locale] ?? catalogs[DEFAULT_LOCALE];

  function interpolate(template: string, params: Params): string {
    return template.replace(/\{([a-z_]+)\}/g, (whole, name: string) => {
      const value = params[name];
      if (value === undefined || value === null) return whole;
      return typeof value === "number" ? formatNumber(locale, value) : value;
    });
  }

  return {
    locale,
    has: (key) => lookup(catalog, key) !== undefined,
    t(key, params = {}) {
      const message = lookup(catalog, key);
      // Clé absente : visible telle quelle (un test vérifie les catalogues).
      if (message === undefined) return key;
      if (typeof message === "string") return interpolate(message, params);
      const count = typeof params.count === "number" ? params.count : 0;
      return interpolate(message[pluralCategory(locale, count)], params);
    },
  };
}
