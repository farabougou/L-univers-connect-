import { badgeStyle, colors } from "@/lib/formStyles";
import { SEVERITIES, SEVERITY_COLOR, type SeverityCounts } from "@/lib/portfolio";

/**
 * Pastilles de gravité (« 2 Critique », « 1 Majeur »...) : une par gravité
 * réellement présente, dans l'ordre de gravité. Sans rien d'ouvert, le texte
 * « Aucune ». Partagé par l'accueil (tuiles et tableau des sites) et la page
 * « Alarmes et constats ».
 */
export function SeverityBadges({
  counts,
  t,
}: {
  counts: SeverityCounts;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const present = SEVERITIES.filter((severity) => counts[severity] > 0);
  if (present.length === 0) {
    return <span style={{ color: colors.textMuted }}>{t("web.dashboard.alerts_none")}</span>;
  }
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
      {present.map((severity) => (
        <span
          key={severity}
          title={t(`severity.${severity}`)}
          style={badgeStyle(SEVERITY_COLOR[severity])}
        >
          {counts[severity]} {t(`severity.${severity}`)}
        </span>
      ))}
    </span>
  );
}
