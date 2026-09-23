/**
 * Passeport d'équipement côté console web : même modèle et mêmes règles que
 * l'application mobile (apps/mobile/src/lib/passport.ts), jamais deux fois
 * la logique de présentation d'un même état.
 */

export type EquipmentStatus = {
  operational_status: string;
  communication_status: string;
  current: boolean;
  as_of: string | null;
  reason: string | null;
};

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

export type Tag = {
  id: string;
  code: string;
  payload: string;
  status: string;
};

export type Passport = {
  node_id: string;
  tags?: Tag[];
  status?: EquipmentStatus | null;
  site?: { id: string; name: string; timezone: string | null } | null;
  node_type: "functional_location" | "physical_unit" | "space" | "point";
  functional_location?: { code: string; name: string };
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
