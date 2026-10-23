import { ASSET_STATUS_COLOR, StatusBadge, type AssetStatus } from "@/components/StatusBadge";
import { colors } from "@/lib/formStyles";

export type HealthBarSegment = {
  status: AssetStatus;
  /** Libellé de l'état, dans la langue de la personne. */
  label: string;
  count: number;
  /** Part du total, de 0 à 100 (voir `healthSegments`). */
  percent: number;
  /** Phrase courte « état : nombre », pour l'infobulle. */
  text: string;
};

/**
 * Barre segmentée de la santé des actifs : un coup d'œil sur la répartition
 * par état, avant le détail par état plus bas dans la page. Chaque segment a
 * la couleur de l'état universel (`ASSET_STATUS_COLOR`) ; la légende reprend la
 * pastille de l'état et le nombre, donc la couleur ne porte jamais le sens
 * seule (directive UI/dashboard, section 33). `ariaLabel` décrit la barre
 * entière pour les lecteurs d'écran.
 */
export function HealthBar({
  segments,
  ariaLabel,
}: {
  segments: HealthBarSegment[];
  ariaLabel: string;
}) {
  return (
    <div>
      <div
        role="img"
        aria-label={ariaLabel}
        style={{
          display: "flex",
          gap: 2,
          height: 14,
          borderRadius: 7,
          overflow: "hidden",
          background: colors.border,
        }}
      >
        {segments.map((segment) => (
          <div
            key={segment.status}
            title={segment.text}
            style={{
              width: `${segment.percent}%`,
              minWidth: 6,
              background: ASSET_STATUS_COLOR[segment.status],
            }}
          />
        ))}
      </div>
      <ul
        style={{
          listStyle: "none",
          display: "flex",
          flexWrap: "wrap",
          gap: "8px 16px",
          margin: "12px 0 0",
          padding: 0,
        }}
      >
        {segments.map((segment) => (
          <li
            key={segment.status}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <StatusBadge status={segment.status} label={segment.label} />
            <span style={{ color: colors.textMuted, fontSize: 13 }}>
              {segment.count}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
