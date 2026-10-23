/**
 * Bloc « Activité récente » du Global Command Center (directive UI/
 * dashboard du 30/09/2026, section 16). Fonctions pures : aucun appel
 * réseau ici. La donnée brute vient de GET /activity/recent (voir
 * apps/web/src/app/page.tsx), qui fusionne côté API interventions, ordres
 * de travail, alarmes, constats et depuis le 02/10/2026 le journal système
 * (app/timeline.py::portfolio_timeline) — jamais un appel par équipement.
 *
 * Volontairement absents aujourd'hui (aucune trace exploitable) :
 * événements énergétiques, incidents (distincts des alarmes, section 24).
 */

import { type Locale, formatDateTime } from "@/i18n/translator";

export type ActivityKind = "alarm" | "finding" | "work_order" | "intervention" | "event";

// Ordre d'affichage des filtres : le plus urgent d'abord, jamais alphabétique.
export const ACTIVITY_KINDS: ActivityKind[] = [
  "alarm",
  "finding",
  "work_order",
  "intervention",
  "event",
];

export type PortfolioTimelineEntry = {
  kind: ActivityKind;
  at: string;
  functional_location_id: string | null;
  reference_id: string;
  title: string | null;
};

export type ActivityFeedEntry = {
  kind: ActivityKind;
  key: string;
  formattedAt: string;
  locationId: string | null;
  locationLabel: string | null;
  title: string | null;
};

/**
 * Transforme la réponse brute de l'API en entrées prêtes à afficher : date
 * formatée dans la langue de la personne, lien résolu seulement si
 * l'équipement existe encore dans le portefeuille (jamais un lien mort).
 */
export function toActivityFeedEntries(
  entries: PortfolioTimelineEntry[],
  locale: Locale,
  locationById: Map<string, { code: string; name: string }>,
): ActivityFeedEntry[] {
  return entries.map((entry) => {
    const location = entry.functional_location_id
      ? locationById.get(entry.functional_location_id)
      : undefined;
    return {
      kind: entry.kind,
      key: `${entry.kind}-${entry.reference_id}`,
      formattedAt: formatDateTime(locale, entry.at),
      locationId: location ? entry.functional_location_id : null,
      locationLabel: location ? `${location.code} — ${location.name}` : null,
      title: entry.title,
    };
  });
}

export type ActivityDetailPart =
  | { type: "location"; id: string; label: string }
  | { type: "title"; text: string };

/**
 * Les éléments connus d'une entrée, après son type : l'équipement (lien) puis
 * le titre. Un élément inconnu n'apparaît pas : l'accueil affichait
 * « Intervention — — » quand ni l'un ni l'autre n'existait, des tirets qui
 * laissaient croire qu'une information manquait à l'écran plutôt qu'au
 * système.
 */
export function activityDetailParts(entry: ActivityFeedEntry): ActivityDetailPart[] {
  const parts: ActivityDetailPart[] = [];
  if (entry.locationId && entry.locationLabel) {
    parts.push({ type: "location", id: entry.locationId, label: entry.locationLabel });
  }
  const title = entry.title?.trim();
  if (title) {
    parts.push({ type: "title", text: title });
  }
  return parts;
}

export function filterActivityEntries(
  entries: ActivityFeedEntry[],
  kinds: ReadonlySet<ActivityKind>,
): ActivityFeedEntry[] {
  return entries.filter((entry) => kinds.has(entry.kind));
}
