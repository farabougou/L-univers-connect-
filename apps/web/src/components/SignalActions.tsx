/**
 * Actions possibles sur une alarme ou un constat (ADR 013, ADR 012 §2.15) :
 * acquitter, retour à la normale (alarme seulement), clore, faux positif,
 * confirmer (constat seulement, jamais une prédiction). Composant partagé
 * entre la fiche équipement (`/registre/{id}`) et la page Alarms & Incidents
 * (`/alarmes`) — chaque page fournit ses propres actions serveur (redirection
 * et revalidation propres à sa propre URL), jamais une action de l'une
 * utilisée par erreur depuis l'autre.
 */

const HANDLING_OPEN = ["open", "in_progress"];

export type SignalActionHandlers = {
  acknowledgeSignal: (formData: FormData) => void | Promise<void>;
  clearAlarm: (formData: FormData) => void | Promise<void>;
  setHandling: (formData: FormData) => void | Promise<void>;
  confirmFinding: (formData: FormData) => void | Promise<void>;
};

export function SignalActions({
  kind,
  signal,
  nodeId,
  actions,
  t,
}: {
  kind: "alarm" | "finding";
  signal: {
    id: string;
    ack_state: string;
    handling_status: string;
    condition_state: string;
    findingKind?: string;
    certainty?: string;
  };
  nodeId: string;
  actions: SignalActionHandlers;
  t: (key: string) => string;
}) {
  const hidden = (
    <>
      <input type="hidden" name="kind" value={kind} />
      <input type="hidden" name="signal_id" value={signal.id} />
      <input type="hidden" name="node_id" value={nodeId} />
    </>
  );
  const handlingOpen = HANDLING_OPEN.includes(signal.handling_status);
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
      {signal.ack_state === "unacknowledged" && (
        <form action={actions.acknowledgeSignal}>
          {hidden}
          <button type="submit">{t("web.registre.acknowledge")}</button>
        </form>
      )}
      {/* Un signalement ne peut être clos tant que sa condition est active
          (voir app/signals.py, set_handling) : seul le retour à la normale
          (alarme) ou le faux positif restent alors possibles. */}
      {kind === "alarm" && signal.condition_state === "active" && (
        <form action={actions.clearAlarm}>
          {hidden}
          <button type="submit">{t("web.registre.clear_condition")}</button>
        </form>
      )}
      {handlingOpen && signal.condition_state === "cleared" && (
        <form action={actions.setHandling}>
          {hidden}
          <input type="hidden" name="handling_status" value="closed" />
          <button type="submit">{t("web.registre.close_signal")}</button>
        </form>
      )}
      {handlingOpen && (
        <form action={actions.setHandling}>
          {hidden}
          <input type="hidden" name="handling_status" value="false_positive" />
          <button type="submit">{t("web.registre.false_positive")}</button>
        </form>
      )}
      {/* Une prédiction porte sur l'avenir : elle n'est jamais confirmée
          (voir app/findings.py, confirm_finding). */}
      {kind === "finding" && signal.certainty !== "confirmed" && signal.findingKind !== "prediction" && (
        <form action={actions.confirmFinding} style={{ display: "flex", gap: 4 }}>
          {hidden}
          <input name="note" required placeholder={t("web.registre.confirm_note")} />
          <button type="submit">{t("web.registre.confirm_finding")}</button>
        </form>
      )}
    </div>
  );
}
