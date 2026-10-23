/**
 * Résumé de la page « Alarmes et constats » : combien de signaux ouverts, par
 * gravité, combien attendent d'être acquittés, combien sont en cours de traitement.
 * Calcul pur sur les listes déjà chargées : aucun appel réseau, aucun texte.
 *
 * Alarmes et constats restent deux notions distinctes (directive UI/dashboard,
 * section 24) : leurs gravités sont comptées séparément. Seuls « à acquitter » et
 * « en cours de traitement » les additionnent, parce que ce sont des tâches pour
 * la même personne, quelle que soit la nature du signal.
 */

import { addSeverity, emptySeverityCounts, type SeverityCounts } from "./portfolio";

type SignalLike = { severity: string; ack_state: string; handling_status: string };

export type SignalsSummary = {
  alarmSeverity: SeverityCounts;
  findingSeverity: SeverityCounts;
  awaitingAck: number;
  inProgress: number;
};

export function summarizeSignals(alarms: SignalLike[], findings: SignalLike[]): SignalsSummary {
  const summary: SignalsSummary = {
    alarmSeverity: emptySeverityCounts(),
    findingSeverity: emptySeverityCounts(),
    awaitingAck: 0,
    inProgress: 0,
  };
  for (const alarm of alarms) addSeverity(summary.alarmSeverity, alarm.severity);
  for (const finding of findings) addSeverity(summary.findingSeverity, finding.severity);
  for (const signal of [...alarms, ...findings]) {
    if (signal.ack_state === "unacknowledged") summary.awaitingAck += 1;
    if (signal.handling_status === "in_progress") summary.inProgress += 1;
  }
  return summary;
}
