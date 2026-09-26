/**
 * Clôture structurée saisie sur le terrain, hors ligne (cahier des charges,
 * section 36 ; codes inspirés d'ISO 14224). Les codes viennent du catalogue
 * partagé `closure.json` : ce sont les mêmes que ceux de l'API, un test côté
 * API vérifie qu'ils correspondent exactement.
 */
import closureFr from "../i18n/fr/closure.json";

export type ClosureSection = "symptoms" | "causes" | "actions" | "verification_results";

export const CLOSURE_CODES: Record<ClosureSection, string[]> = {
  symptoms: Object.keys(closureFr.symptoms),
  causes: Object.keys(closureFr.causes),
  actions: Object.keys(closureFr.actions),
  verification_results: Object.keys(closureFr.verification_results),
};

export type ClosurePartDraft = { reference: string; quantity: string };

export type ClosureDraft = {
  symptom_code: string | null;
  cause_code: string | null;
  action_code: string | null;
  verification_result: string | null;
  labor_minutes: string;
  parts: ClosurePartDraft[];
  note: string;
};

export type ClosureBody = {
  symptom_code: string;
  cause_code: string;
  action_code: string;
  verification_result: string;
  labor_minutes: number;
  parts: { reference: string; quantity: number }[];
  note?: string;
};

export const EMPTY_CLOSURE: ClosureDraft = {
  symptom_code: null,
  cause_code: null,
  action_code: null,
  verification_result: null,
  labor_minutes: "",
  parts: [],
  note: "",
};

const MAX_LABOR_MINUTES = 10080;

/**
 * Mêmes règles que l'API, vérifiées avant l'enregistrement local : une
 * clôture refusée plus tard par le serveur resterait bloquée dans la file.
 * Renvoie la clé du message d'erreur, ou `null` si la clôture est valide.
 */
export function validateClosure(draft: ClosureDraft): string | null {
  const prefix = "mobile.intervention.closure.";
  const codes = [draft.symptom_code, draft.cause_code, draft.action_code, draft.verification_result];
  if (codes.some((code) => !code) || draft.labor_minutes.trim() === "") {
    return `${prefix}incomplete`;
  }
  const minutes = Number(draft.labor_minutes);
  if (!Number.isInteger(minutes) || minutes < 0 || minutes > MAX_LABOR_MINUTES) {
    return `${prefix}labor_invalid`;
  }
  const partsValid = draft.parts.every(
    (part) => part.reference.trim() !== "" && Number(part.quantity.replace(",", ".")) > 0,
  );
  if (!partsValid) return `${prefix}part_invalid`;
  if (draft.action_code === "replacement" && draft.parts.length === 0) {
    return `${prefix}replacement_requires_parts`;
  }
  return null;
}

/** Corps envoyé à l'API ; à n'appeler qu'après `validateClosure`. */
export function toClosureBody(draft: ClosureDraft): ClosureBody {
  const body: ClosureBody = {
    symptom_code: draft.symptom_code as string,
    cause_code: draft.cause_code as string,
    action_code: draft.action_code as string,
    verification_result: draft.verification_result as string,
    labor_minutes: Number(draft.labor_minutes),
    parts: draft.parts.map((part) => ({
      reference: part.reference.trim(),
      quantity: Number(part.quantity.replace(",", ".")),
    })),
  };
  const note = draft.note.trim();
  if (note) body.note = note;
  return body;
}
