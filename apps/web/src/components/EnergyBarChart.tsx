import { colors } from "@/lib/formStyles";

/**
 * Visualisation orientée décision (directive Command Center, ADR 014 §36.2,
 * feature-benchmark-matrix.md, ligne « Visualisation de données orientée
 * décision ») : consommation brute et consommation normalisée (corrigée des
 * degrés-jours), période par période — la donnée existe déjà (`app/energy/`)
 * et s'affichait jusqu'ici seulement en texte pour la dernière période.
 *
 * SVG construit à la main, sans bibliothèque de graphiques (ADR 014,
 * ligne « Design System commun » : aucune dépendance structurante ajoutée
 * sans besoin réel vérifié) — un graphique à barres groupées suffit ici,
 * jamais un prétexte pour ajouter une dépendance avant qu'elle ne soit
 * nécessaire.
 */
const WIDTH = 320;
const HEIGHT = 140;
const AXIS_HEIGHT = 20;

export type EnergyChartPeriod = {
  label: string;
  raw: number;
  normalized: number | null;
};

export function EnergyBarChart({
  periods,
  unit,
  rawLabel,
  normalizedLabel,
}: {
  periods: EnergyChartPeriod[];
  unit: string;
  rawLabel: string;
  normalizedLabel: string;
}) {
  if (periods.length === 0) return null;
  const hasNormalized = periods.some((period) => period.normalized !== null);
  const maxValue = Math.max(
    1,
    ...periods.flatMap((period) => [period.raw, period.normalized ?? 0]),
  );
  const slotWidth = WIDTH / periods.length;
  const barWidth = hasNormalized ? slotWidth / 3.2 : slotWidth / 1.8;
  const plotHeight = HEIGHT - AXIS_HEIGHT;

  function barHeight(value: number): number {
    return (value / maxValue) * plotHeight;
  }

  return (
    <div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", maxWidth: 480, height: "auto" }}
        role="img"
        aria-label={`${rawLabel}${hasNormalized ? `, ${normalizedLabel}` : ""} (${unit})`}
      >
        {periods.map((period, index) => {
          const slotX = index * slotWidth;
          const rawHeight = barHeight(period.raw);
          const rawX = slotX + slotWidth / 2 - (hasNormalized ? barWidth + 1 : barWidth / 2);
          return (
            <g key={index}>
              <rect
                x={rawX}
                y={plotHeight - rawHeight}
                width={barWidth}
                height={rawHeight}
                fill={colors.accent}
              />
              {period.normalized !== null && (
                <rect
                  x={slotX + slotWidth / 2 + 1}
                  y={plotHeight - barHeight(period.normalized)}
                  width={barWidth}
                  height={barHeight(period.normalized)}
                  fill={colors.textMuted}
                />
              )}
              <text
                x={slotX + slotWidth / 2}
                y={HEIGHT - 6}
                fontSize={8}
                textAnchor="middle"
                fill={colors.textMuted}
              >
                {period.label}
              </text>
            </g>
          );
        })}
      </svg>
      <p style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
        <span style={{ color: colors.accent }}>■</span> {rawLabel}
        {hasNormalized && (
          <>
            {"  "}
            <span style={{ color: colors.textMuted }}>■</span> {normalizedLabel}
          </>
        )}
      </p>
    </div>
  );
}
