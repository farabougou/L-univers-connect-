/**
 * Passeport numérique d'un équipement, consulté en ligne après lecture d'une
 * étiquette (ADR 012, étape F5).
 *
 * L'étiquette ne contient qu'un code opaque (`paios:tag:<code>`). Le serveur
 * décide de tout : ce qui s'affiche et les actions permises dépendent des
 * droits de la personne connectée. L'application n'en déduit jamais rien
 * d'elle-même, et aucune action de commande d'équipement n'existe.
 */

export const QR_PREFIX = "paios:tag:";

// Même alphabet que secrets.token_urlsafe côté serveur.
const CODE_PATTERN = /^[A-Za-z0-9_-]{8,64}$/;

/** Accepte le contenu brut d'un QR ou le code tapé à la main. */
export function parseTagCode(input: string): string | null {
  let code = input.trim();
  if (code.startsWith(QR_PREFIX)) {
    code = code.slice(QR_PREFIX.length);
  }
  return CODE_PATTERN.test(code) ? code : null;
}

export type PassportMeasurement = {
  value: number;
  measured_at: string;
  quality_flags: string[];
};

export type PassportPoint = {
  id: string;
  code: string;
  name: string;
  unit: string;
  mapping_status: string;
  latest: PassportMeasurement | null;
};

export type PassportUnit = {
  id: string;
  serial_number: string;
  lifecycle_state: string;
  manufacturer: string;
  reference: string;
  category: string;
};

export type Passport = {
  node_id: string;
  node_type: "functional_location" | "physical_unit" | "space" | "point";
  allowed_actions: string[];
  functional_location?: { code: string; name: string };
  space_path?: { name: string }[];
  current_unit?: PassportUnit | null;
  physical_unit?: PassportUnit | null;
  points?: PassportPoint[];
  open_findings: {
    id: string;
    severity: string;
    title: string;
    certainty: string;
    condition_state: string;
    ack_state: string;
    handling_status: string;
  }[];
  open_alarms?: {
    id: string;
    severity: string;
    message: string;
    condition_state: string;
    ack_state: string;
    handling_status: string;
  }[];
  open_work_orders?: { id: string; title: string; status: string }[];
  recent_interventions?: {
    id: string;
    started_at: string;
    summary: string | null;
    symptom_label: string | null;
    action_label: string | null;
  }[];
};

export type ScanResult =
  | { ok: true; passport: Passport }
  | { ok: false; message: string };

/** Traduit la réponse du serveur en message clair pour le technicien. */
export async function fetchPassportByTag(
  apiUrl: string,
  accessToken: string,
  code: string,
): Promise<ScanResult> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/tags/${encodeURIComponent(code)}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch {
    return { ok: false, message: "Pas de réseau : le passeport se consulte en ligne." };
  }
  if (response.ok) {
    const body = (await response.json()) as { passport: Passport };
    return { ok: true, passport: body.passport };
  }
  switch (response.status) {
    case 404:
      return { ok: false, message: "Étiquette inconnue." };
    case 410:
      return {
        ok: false,
        message: "Étiquette révoquée : scannez la nouvelle étiquette de l'équipement.",
      };
    case 401:
    case 403:
      return { ok: false, message: "Accès refusé : reconnectez-vous." };
    default:
      return { ok: false, message: `Erreur serveur (${response.status}).` };
  }
}

const LIFECYCLE_LABELS: Record<string, string> = {
  planned: "Prévu",
  ordered: "Commandé",
  in_stock: "En stock",
  installed: "Installé",
  commissioned: "Mis en service (réception)",
  in_service: "En service",
  out_of_service: "Hors service",
  removed: "Déposé",
  decommissioned: "Réformé",
  disposed: "Éliminé",
};

export function lifecycleLabel(state: string): string {
  return LIFECYCLE_LABELS[state] ?? state;
}
