import Link from "next/link";

import { type Locale, formatDateTime } from "@/i18n/translator";
import { colors } from "@/lib/formStyles";

/**
 * Chronologie fusionnée d'un actif (directive UI/dashboard du 30/09/2026,
 * section 22 : « la timeline doit être un composant central partagé »).
 * Extrait de la fiche équipement (`/registre/{id}`), où elle vivait comme
 * une section isolée avant ce lot (section 36, point 3) — même donnée
 * (`GET /graph/nodes/{id}/timeline`, app/timeline.py), même comportement,
 * désormais réutilisable par toute future page qui a besoin d'un historique
 * fusionné pour un équipement ou un exemplaire donné.
 *
 * Pagination par curseur de date (`before`), jamais tout l'historique d'un
 * actif chargé d'un coup — le composant ne décide que d'afficher ou non le
 * lien « voir plus ancien » (`loadOlderHref`), la page appelante construit
 * l'URL réelle.
 */
export type TimelineEntry = {
  kind: "intervention" | "work_order" | "alarm" | "finding" | "lifecycle" | "event";
  at: string;
  reference_id: string;
  title: string | null;
  field: string | null;
  status: string | null;
  changed_by: string | null;
  note: string | null;
};

// Catalogue à utiliser pour traduire `status` selon le `field` d'une entrée :
// les mêmes catalogues déjà affichés ailleurs (statut de fonctionnement,
// cycle de vie…), jamais une nouvelle traduction inventée pour la timeline.
const TIMELINE_STATUS_CATALOG: Record<string, string> = {
  lifecycle_state: "lifecycle",
  handling_status: "handling_status",
  condition_state: "condition_state",
  ack_state: "ack_state",
  certainty: "certainty",
  intervention_type: "intervention_type",
};

export function timelineStatusLabel(
  entry: TimelineEntry,
  t: (key: string, params?: Record<string, string>) => string,
): string | null {
  if (!entry.status) return null;
  if (entry.kind === "event") {
    // Le titre de l'événement (`app/timeline.py`, `_render_event_title`)
    // contient déjà tout ce qu'il y a à dire ; `status` ne porte que le
    // code stable (ex. DEVICE_WENT_OFFLINE), jamais affiché brut (ADR 013).
    return null;
  }
  if (entry.kind === "work_order" && entry.field === "status") {
    return t(`work_order.status.${entry.status}`);
  }
  const catalog = entry.field ? TIMELINE_STATUS_CATALOG[entry.field] : undefined;
  return catalog ? t(`${catalog}.${entry.status}`) : entry.status;
}

export function Timeline({
  entries,
  timeZone,
  locale,
  loadOlderHref,
  t,
}: {
  entries: TimelineEntry[];
  timeZone: string | null;
  locale: Locale;
  loadOlderHref: string | null;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  if (entries.length === 0) {
    return <p style={{ color: colors.textMuted }}>{t("timeline.empty")}</p>;
  }
  return (
    <>
      {entries.map((entry) => {
        const status = timelineStatusLabel(entry, t);
        return (
          <p key={`${entry.kind}-${entry.reference_id}-${entry.at}`} style={{ margin: "0 0 8px" }}>
            <span style={{ color: colors.textMuted }}>
              {formatDateTime(locale, entry.at, timeZone)}
            </span>
            {" — "}
            <span style={{ fontWeight: 600 }}>{t(`timeline.kind_${entry.kind}`)}</span>
            {entry.title && ` — ${entry.title}`}
            {!entry.title && status && ` — ${status}`}
            {entry.title && status && ` (${status})`}
            {entry.changed_by && ` — ${t("timeline.by", { actor: entry.changed_by })}`}
            {entry.note && (
              <>
                <br />
                {entry.note}
              </>
            )}
          </p>
        );
      })}
      {loadOlderHref && (
        <Link href={loadOlderHref} style={{ color: colors.accent }}>
          {t("timeline.load_older")}
        </Link>
      )}
    </>
  );
}
