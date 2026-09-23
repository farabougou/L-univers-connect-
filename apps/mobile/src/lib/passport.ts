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
  asset_code: string | null;
  lifecycle_state: string;
  manufacturer: string;
  reference: string;
  equipment_type: string;
  manufacturer_designation: string | null;
};

export type EquipmentStatus = {
  operational_status: string;
  communication_status: string;
  current: boolean;
  as_of: string | null;
  reason: string | null;
};

export type Passport = {
  node_id: string;
  status?: EquipmentStatus | null;
  site?: { id: string; name: string; timezone: string | null } | null;
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
  | { ok: false; messageKey: string; params?: Record<string, number> };

/** Réponse du serveur → clé du message à afficher (catalogue d'interface). */
export async function fetchPassportByTag(
  apiUrl: string,
  accessToken: string,
  code: string,
  language: string,
): Promise<ScanResult> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/tags/${encodeURIComponent(code)}`, {
      // La langue demandée sert aux titres des constats, traduits par l'API.
      headers: { Authorization: `Bearer ${accessToken}`, "Accept-Language": language },
    });
  } catch {
    return { ok: false, messageKey: "mobile.passport.offline" };
  }
  if (response.ok) {
    const body = (await response.json()) as { passport: Passport };
    return { ok: true, passport: body.passport };
  }
  switch (response.status) {
    case 404:
      return { ok: false, messageKey: "mobile.passport.tag_unknown" };
    case 410:
      return { ok: false, messageKey: "mobile.passport.tag_revoked" };
    case 401:
    case 403:
      return { ok: false, messageKey: "mobile.passport.forbidden" };
    default:
      return {
        ok: false,
        messageKey: "mobile.passport.server_error",
        params: { status: response.status },
      };
  }
}

/**
 * Phrase d'état : jamais un état présenté comme actuel sans donnée récente
 * (ADR 013, 4.5). Renvoie la clé du catalogue et ses paramètres.
 */
export function statusMessage(
  status: EquipmentStatus,
): { key: string; params?: Record<string, string> } {
  if (status.reason === "no_status_point") return { key: "mobile.passport.status_no_point" };
  if (status.reason === "no_measurement" || !status.as_of) {
    return { key: "mobile.passport.status_no_measurement" };
  }
  const state = `operational_status.${status.operational_status}`;
  if (status.current) {
    return {
      key: "mobile.passport.status_current",
      params: { state, communication: `communication_status.${status.communication_status}` },
    };
  }
  return {
    key:
      status.communication_status === "offline"
        ? "mobile.passport.status_offline"
        : "mobile.passport.status_unverified",
    params: { state, since: status.as_of },
  };
}
