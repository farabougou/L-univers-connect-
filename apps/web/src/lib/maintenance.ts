/**
 * Agrégation pure pour le bloc « Maintenance » du Global Command Center
 * (directive UI/dashboard du 30/09/2026, section 12). Aucun appel réseau
 * ici, pour rester testable sans backend (voir maintenance.test.ts).
 *
 * « Interventions en retard » n'est volontairement pas calculé : les ordres
 * de travail n'ont aujourd'hui aucune date d'échéance enregistrée
 * (`work_orders` n'a pas de colonne correspondante) — jamais une donnée
 * inventée pour remplir une case (directive, section 37).
 */

export type MaintenanceWorkOrder = {
  id: string;
  functional_location_id: string | null;
  title: string;
  work_order_type: string;
  priority: string;
  status: string;
};

export type MaintenanceIntervention = {
  id: string;
  functional_location_id: string | null;
  technician: string;
  summary: string | null;
  ended_at: string | null;
};

const OPEN_STATUSES = new Set(["open", "in_progress"]);

export function countInProgress(workOrders: MaintenanceWorkOrder[]): number {
  return workOrders.filter((wo) => wo.status === "in_progress").length;
}

export function countCriticalOpen(workOrders: MaintenanceWorkOrder[]): number {
  return workOrders.filter((wo) => wo.priority === "urgent" && OPEN_STATUSES.has(wo.status)).length;
}

export type RepeatingFailure = { functional_location_id: string; count: number };

/**
 * Équipements dont au moins `minOccurrences` ordres de travail correctifs
 * ont déjà été ouverts (tous statuts confondus) — un signal de panne
 * répétitive, pas une affirmation de cause commune.
 */
export function repeatingFailures(
  workOrders: MaintenanceWorkOrder[],
  minOccurrences = 2,
): RepeatingFailure[] {
  const counts = new Map<string, number>();
  for (const wo of workOrders) {
    if (wo.work_order_type !== "corrective" || !wo.functional_location_id) continue;
    counts.set(wo.functional_location_id, (counts.get(wo.functional_location_id) ?? 0) + 1);
  }
  return [...counts.entries()]
    .filter(([, count]) => count >= minOccurrences)
    .map(([functional_location_id, count]) => ({ functional_location_id, count }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Dernières clôtures réelles : une intervention dont `ended_at` est
 * renseigné, la plus récente d'abord — jamais une date de clôture déduite
 * du statut de l'ordre de travail, qui n'existe pas.
 */
export function recentClosures(
  interventions: MaintenanceIntervention[],
  limit: number,
): MaintenanceIntervention[] {
  return interventions
    .filter((intervention) => intervention.ended_at !== null)
    .sort((a, b) => (b.ended_at as string).localeCompare(a.ended_at as string))
    .slice(0, limit);
}
