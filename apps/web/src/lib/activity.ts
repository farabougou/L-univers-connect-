/**
 * Bloc « Activité récente » du Global Command Center (directive UI/
 * dashboard du 30/09/2026, section 16). Fonctions pures : aucun appel
 * réseau ici. La donnée brute vient de GET /activity/recent (voir
 * apps/web/src/app/page.tsx), qui fusionne côté API interventions, ordres
 * de travail, alarmes et constats pour tout le portefeuille
 * (app/timeline.py::portfolio_timeline) — jamais un appel par équipement.
 *
 * Volontairement absents aujourd'hui (aucune trace exploitable) :
 * changements d'état d'équipement, événements énergétiques, incidents ; et
 * présents côté système mais pas encore raccordés ici : événements Edge,
 * changements de connectivité, commandes (voir la table `events` et
 * app/events.py) — DEFER, documenté dans la matrice plutôt qu'ignoré.
 */

import { type Locale, formatDateTime } from "@/i18n/translator";

export type ActivityKind = "alarm" | "finding" | "work_order" | "intervention";

// Ordre d'affichage des filtres : le plus urgent d'abord, jamais alphabétique.
export const ACTIVITY_KINDS: ActivityKind[] = ["alarm", "finding", "work_order", "intervention"];

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

export function filterActivityEntries(
  entries: ActivityFeedEntry[],
  kinds: ReadonlySet<ActivityKind>,
): ActivityFeedEntry[] {
  return entries.filter((entry) => kinds.has(entry.kind));
}
