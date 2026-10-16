/**
 * Fiche d'intervention fluides frigorigènes fluorés (CERFA 15497*04),
 * saisie sur le terrain, hors ligne — même principe que la clôture
 * structurée (closure.ts). Les codes viennent du catalogue partagé
 * `fgas.json` : ce sont les mêmes que ceux de l'API, un test côté API
 * vérifie qu'ils correspondent exactement.
 */
import fgasFr from "../i18n/fr/fgas.json";

export type FgasSection = "nature_of_intervention" | "waste_classification";

export const FGAS_CODES: Record<FgasSection, string[]> = {
  nature_of_intervention: Object.keys(fgasFr.nature_of_intervention),
  waste_classification: Object.keys(fgasFr.waste_classification),
};

export type FgasLeakDraft = { location: string; repaired: boolean | null };

export type FgasDraft = {
  fiche_number: string;
  operator_name: string;
  operator_address: string;
  operator_siret: string;
  operator_capacity_number: string;
  detenteur_name: string;
  detenteur_address: string;
  detenteur_siret: string;
  equipment_identification: string;
  refrigerant_name: string;
  total_charge_kg: string;
  co2_equivalent_tonnes: string;
  nature_of_intervention: string[];
  nature_other_detail: string;
  manual_leak_detector_identification: string;
  manual_leak_detector_checked_on: string;
  permanent_detection_system: boolean | null;
  leaks_found: boolean | null;
  leaks: FgasLeakDraft[];
  charged_virgin_kg: string;
  charged_recycled_kg: string;
  charged_regenerated_kg: string;
  charged_fluid_name_if_changed: string;
  recovered_for_treatment_kg: string;
  recovered_for_reuse_kg: string;
  bsff_number: string;
  container_identification: string;
  waste_classification: string[];
  waste_classification_other_non_flammable: string;
  waste_classification_other_flammable: string;
  destination_installation: string;
  observations: string;
  operator_signatory_name: string;
  operator_signatory_role: string;
  detenteur_signatory_name: string;
  detenteur_signatory_role: string;
  signed_at: string;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function emptyFgas(): FgasDraft {
  return {
    fiche_number: "",
    operator_name: "",
    operator_address: "",
    operator_siret: "",
    operator_capacity_number: "",
    detenteur_name: "",
    detenteur_address: "",
    detenteur_siret: "",
    equipment_identification: "",
    refrigerant_name: "",
    total_charge_kg: "",
    co2_equivalent_tonnes: "",
    nature_of_intervention: [],
    nature_other_detail: "",
    manual_leak_detector_identification: "",
    manual_leak_detector_checked_on: "",
    permanent_detection_system: null,
    leaks_found: null,
    leaks: [],
    charged_virgin_kg: "0",
    charged_recycled_kg: "0",
    charged_regenerated_kg: "0",
    charged_fluid_name_if_changed: "",
    recovered_for_treatment_kg: "0",
    recovered_for_reuse_kg: "0",
    bsff_number: "",
    container_identification: "",
    waste_classification: [],
    waste_classification_other_non_flammable: "",
    waste_classification_other_flammable: "",
    destination_installation: "",
    observations: "",
    operator_signatory_name: "",
    operator_signatory_role: "",
    detenteur_signatory_name: "",
    detenteur_signatory_role: "",
    signed_at: today(),
  };
}

function toNumber(value: string): number {
  return Number(value.replace(",", "."));
}

function isNonNegativeNumber(value: string): boolean {
  const n = toNumber(value);
  return value.trim() !== "" && Number.isFinite(n) && n >= 0;
}

/**
 * Mêmes règles que l'API, vérifiées avant l'enregistrement local : une
 * fiche refusée plus tard par le serveur resterait bloquée dans la file.
 * Renvoie la clé du message d'erreur, ou `null` si la fiche est valide.
 */
export function validateFgas(draft: FgasDraft): string | null {
  const prefix = "mobile.intervention.fgas.";
  if (
    !draft.operator_name.trim() ||
    !draft.detenteur_name.trim() ||
    !draft.equipment_identification.trim() ||
    !draft.refrigerant_name.trim() ||
    !draft.operator_signatory_name.trim() ||
    !draft.signed_at.trim()
  ) {
    return `${prefix}incomplete`;
  }
  if (!isNonNegativeNumber(draft.total_charge_kg)) {
    return `${prefix}total_charge_invalid`;
  }
  if (draft.nature_of_intervention.length === 0) {
    return `${prefix}nature_required`;
  }
  if (draft.nature_of_intervention.includes("other") && !draft.nature_other_detail.trim()) {
    return `${prefix}nature_other_detail_required`;
  }
  if (
    draft.waste_classification.includes("other_non_flammable") &&
    !draft.waste_classification_other_non_flammable.trim()
  ) {
    return `${prefix}waste_other_detail_required`;
  }
  if (
    draft.waste_classification.includes("other_flammable") &&
    !draft.waste_classification_other_flammable.trim()
  ) {
    return `${prefix}waste_other_detail_required`;
  }
  if (draft.leaks.some((leak) => !leak.location.trim())) {
    return `${prefix}leak_location_required`;
  }
  for (const field of [
    draft.charged_virgin_kg,
    draft.charged_recycled_kg,
    draft.charged_regenerated_kg,
    draft.recovered_for_treatment_kg,
    draft.recovered_for_reuse_kg,
  ]) {
    if (!isNonNegativeNumber(field)) {
      return `${prefix}quantity_invalid`;
    }
  }
  if (draft.co2_equivalent_tonnes.trim() && !isNonNegativeNumber(draft.co2_equivalent_tonnes)) {
    return `${prefix}quantity_invalid`;
  }
  return null;
}

/** Corps envoyé à l'API ; à n'appeler qu'après `validateFgas`. */
export function toFgasBody(draft: FgasDraft): Record<string, unknown> {
  const optional = (value: string) => (value.trim() ? value.trim() : null);
  return {
    fiche_number: optional(draft.fiche_number),
    operator_name: draft.operator_name.trim(),
    operator_address: optional(draft.operator_address),
    operator_siret: optional(draft.operator_siret),
    operator_capacity_number: optional(draft.operator_capacity_number),
    detenteur_name: draft.detenteur_name.trim(),
    detenteur_address: optional(draft.detenteur_address),
    detenteur_siret: optional(draft.detenteur_siret),
    equipment_identification: draft.equipment_identification.trim(),
    refrigerant_name: draft.refrigerant_name.trim(),
    total_charge_kg: toNumber(draft.total_charge_kg),
    co2_equivalent_tonnes: draft.co2_equivalent_tonnes.trim()
      ? toNumber(draft.co2_equivalent_tonnes)
      : null,
    nature_of_intervention: draft.nature_of_intervention,
    nature_other_detail: optional(draft.nature_other_detail),
    manual_leak_detector_identification: optional(draft.manual_leak_detector_identification),
    manual_leak_detector_checked_on: draft.manual_leak_detector_checked_on.trim() || null,
    permanent_detection_system: draft.permanent_detection_system,
    leaks_found: draft.leaks_found,
    leaks: draft.leaks.map((leak) => ({
      location: leak.location.trim(),
      repaired: leak.repaired,
    })),
    charged_virgin_kg: toNumber(draft.charged_virgin_kg),
    charged_recycled_kg: toNumber(draft.charged_recycled_kg),
    charged_regenerated_kg: toNumber(draft.charged_regenerated_kg),
    charged_fluid_name_if_changed: optional(draft.charged_fluid_name_if_changed),
    recovered_for_treatment_kg: toNumber(draft.recovered_for_treatment_kg),
    recovered_for_reuse_kg: toNumber(draft.recovered_for_reuse_kg),
    bsff_number: optional(draft.bsff_number),
    container_identification: optional(draft.container_identification),
    waste_classification: draft.waste_classification,
    waste_classification_other_non_flammable: optional(
      draft.waste_classification_other_non_flammable,
    ),
    waste_classification_other_flammable: optional(draft.waste_classification_other_flammable),
    destination_installation: optional(draft.destination_installation),
    observations: optional(draft.observations),
    operator_signatory_name: draft.operator_signatory_name.trim(),
    operator_signatory_role: optional(draft.operator_signatory_role),
    detenteur_signatory_name: optional(draft.detenteur_signatory_name),
    detenteur_signatory_role: optional(draft.detenteur_signatory_role),
    signed_at: draft.signed_at.trim(),
  };
}
