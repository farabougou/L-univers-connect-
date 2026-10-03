/**
 * Alertes ouvertes (alarmes + constats) du tenant — écran terrain « Alertes »
 * (app/alertes.tsx). Même source et même tri que la page web /alarmes
 * (apps/web/src/app/alarmes/page.tsx, apps/web/src/lib/portfolio.ts) : un
 * technicien sur le terrain voit le même portefeuille qu'un responsable au
 * bureau, jamais une liste recalculée différemment.
 *
 * Pas de lien direct vers le passeport de l'équipement depuis cette liste :
 * le passeport mobile se consulte par étiquette (QR ou code, voir
 * `fetchPassportByTag`), jamais par identifiant brut — DEFER tant qu'aucun
 * besoin réel de « sauter » directement d'une alerte au passeport n'est
 * confirmé (afficher un lien qui ne mène nulle part serait pire que pas de
 * lien du tout).
 */

export type Alert = {
  id: string;
  kind: "alarm" | "finding";
  equipmentCode: string | null;
  equipmentName: string | null;
  severity: string;
  message: string;
  ackState: string;
  raisedAt: string;
};

type RawAlarm = {
  id: string;
  functional_location_id: string | null;
  severity: string;
  message: string;
  ack_state: string;
  raised_at: string;
};

type RawFinding = {
  id: string;
  subject_node_id: string;
  severity: string;
  title: string;
  ack_state: string;
  last_seen_at: string;
};

type FunctionalLocation = { id: string; code: string; name: string };

// Même ordre de priorité que web (apps/web/src/lib/portfolio.ts,
// SEVERITY_RANK) : une alerte critique toujours avant une majeure, même
// plus ancienne.
const SEVERITY_RANK: Record<string, number> = { critical: 0, major: 1, warning: 2, info: 3 };

async function fetchOpenSignals<T>(
  apiUrl: string,
  accessToken: string,
  path: string,
): Promise<T[]> {
  const results = await Promise.all(
    ["open", "in_progress"].map(async (handlingStatus) => {
      const response = await fetch(`${apiUrl}${path}?handling_status=${handlingStatus}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      return response.ok ? ((await response.json()) as T[]) : [];
    }),
  );
  return results.flat();
}

export async function fetchOpenAlerts(apiUrl: string, accessToken: string): Promise<Alert[]> {
  const [alarms, findings, locationsResponse] = await Promise.all([
    fetchOpenSignals<RawAlarm>(apiUrl, accessToken, "/alarms"),
    fetchOpenSignals<RawFinding>(apiUrl, accessToken, "/findings"),
    fetch(`${apiUrl}/functional-locations`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    }),
  ]);
  const locationList: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const locationById = new Map(locationList.map((location) => [location.id, location]));

  const alerts: Alert[] = [
    ...alarms.map((alarm) => {
      const location = alarm.functional_location_id
        ? locationById.get(alarm.functional_location_id)
        : undefined;
      return {
        id: alarm.id,
        kind: "alarm" as const,
        equipmentCode: location?.code ?? null,
        equipmentName: location?.name ?? null,
        severity: alarm.severity,
        message: alarm.message,
        ackState: alarm.ack_state,
        raisedAt: alarm.raised_at,
      };
    }),
    ...findings.map((finding) => {
      const location = locationById.get(finding.subject_node_id);
      return {
        id: finding.id,
        kind: "finding" as const,
        equipmentCode: location?.code ?? null,
        equipmentName: location?.name ?? null,
        severity: finding.severity,
        message: finding.title,
        ackState: finding.ack_state,
        raisedAt: finding.last_seen_at,
      };
    }),
  ];

  return alerts.sort((a, b) => {
    const bySeverity = (SEVERITY_RANK[a.severity] ?? 99) - (SEVERITY_RANK[b.severity] ?? 99);
    return bySeverity !== 0 ? bySeverity : a.raisedAt.localeCompare(b.raisedAt);
  });
}
