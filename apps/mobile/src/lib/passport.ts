/**
 * Passeport numérique d'un équipement, consulté en ligne après lecture d'une
 * étiquette (ADR 012, étape F5).
 *
 * L'étiquette ne contient qu'un code opaque (`paios:tag:<code>`). Le serveur
 * décide de tout : ce qui s'affiche et les actions permises dépendent des
 * droits de la personne connectée. L'application n'en déduit jamais rien
 * d'elle-même.
 *
 * Exception scopée à la règle non négociable 1 (CLAUDE.md, décision de
 * Mohamed du 24/09/2026) : une commande peut être envoyée à un appareil
 * explicitement simulé, jamais à un équipement réel — voir `sendCommand` et
 * `fetchSimulatedRelayPointId`. Les trois rôles de la plateforme
 * (technicien, responsable_exploitation, admin_tenant) y sont tous
 * autorisés (`_COMMAND_ROLES`, app/routers/commands.py) : pas de filtrage
 * par rôle ici tant qu'aucun rôle n'en est exclu — l'API reste la seule
 * autorité si ça change un jour.
 */

export const QR_PREFIX = "paios:tag:";

// Même alphabet que secrets.token_urlsafe côté serveur.
const CODE_PATTERN = /^[A-Za-z0-9_-]{8,64}$/;

/** Un QR lu par l'appareil photo est-il une étiquette de la plateforme ? */
export function isPlatformTag(scanned: string): boolean {
  return scanned.trim().startsWith(QR_PREFIX) && parseTagCode(scanned) !== null;
}

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

export type DesiredState = {
  id: string;
  point_id: string;
  value: number;
  valid_from: string;
  valid_to: string | null;
};

// Statuts possibles pour une commande (app/commands.py) : "unconfirmed" est
// calculé à la lecture par l'API, jamais stocké tel quel.
export type PassportCommand = {
  id: string;
  point_id: string;
  requested_value: number;
  status: string;
  actual_value: number | null;
  failure_reason: string | null;
  created_at: string;
};

export type PassportPoint = {
  id: string;
  code: string;
  name: string;
  unit: string;
  mapping_status: string;
  latest: PassportMeasurement | null;
  // État souhaité déclaré (app/desired_states.py) et commandes de test
  // (app/commands.py) — deux notions distinctes du jumeau numérique du
  // point, jamais confondues (mêmes types que apps/web/src/lib/passport.ts).
  desired_states: DesiredState[];
  commands: PassportCommand[];
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
 * Le point pilotable par une commande de test est celui visé par la
 * connexion Modbus active de type "simulated_relay" (jamais un vrai
 * appareil) — même règle que apps/web/src/app/registre/[id]/page.tsx :
 * `point_class` seul ne suffit pas, il faut une connexion réellement active
 * pour qu'une commande ait un appareil qui la reçoive.
 */
export async function fetchSimulatedRelayPointId(
  apiUrl: string,
  accessToken: string,
  functionalLocationId: string,
): Promise<string | null> {
  let response: Response;
  try {
    response = await fetch(
      `${apiUrl}/configs?config_type=modbus_device_mapping&subject_key=${encodeURIComponent(
        functionalLocationId,
      )}`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
  } catch {
    return null;
  }
  if (!response.ok) return null;
  const versions = (await response.json()) as {
    status: string;
    content: { device_type: string; points: { point_id: string }[] };
  }[];
  const active = versions.find(
    (version) => version.status === "active" && version.content.device_type === "simulated_relay",
  );
  return active?.content.points[0]?.point_id ?? null;
}

export type CommandResult =
  | { ok: true; command: PassportCommand }
  | { ok: false; messageKey: string; params?: Record<string, number> };

/**
 * Déclenche une commande de test (voir app/commands.py) : l'API refuse
 * elle-même toute cible qui ne serait pas un appareil explicitement simulé,
 * cet appel ne fait qu'atteindre la même route que la console web.
 */
export async function sendCommand(
  apiUrl: string,
  accessToken: string,
  pointId: string,
  requestedValue: number,
): Promise<CommandResult> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/commands`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ point_id: pointId, requested_value: requestedValue }),
    });
  } catch {
    return { ok: false, messageKey: "mobile.passport.offline" };
  }
  if (response.ok) {
    const command = (await response.json()) as PassportCommand;
    return { ok: true, command };
  }
  return {
    ok: false,
    messageKey: "mobile.passport.server_error",
    params: { status: response.status },
  };
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
