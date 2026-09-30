/**
 * Symbole de marque Enoryx (Physical Asset Intelligence OS) : noyau =
 * intelligence, anneaux orbitaux = supervision continue, nœuds = actifs
 * connectés. Inline (pas une balise <img>) pour que `variant="mono"` hérite
 * la couleur du texte environnant via `currentColor` — premier composant
 * partagé de `apps/web/src/components/` (ADR 014, Design System commun).
 */
export function EnoryxMark({
  variant = "glow",
  size = 32,
}: {
  variant?: "glow" | "mono";
  size?: number;
}) {
  if (variant === "mono") {
    return (
      <svg
        viewBox="0 0 200 200"
        width={size}
        height={size}
        role="img"
        aria-label="Enoryx"
      >
        <g fill="none" stroke="currentColor" strokeWidth={6}>
          <ellipse cx={100} cy={100} rx={88} ry={40} />
          <ellipse cx={100} cy={100} rx={88} ry={40} transform="rotate(60 100 100)" />
          <ellipse cx={100} cy={100} rx={88} ry={40} transform="rotate(120 100 100)" />
        </g>
        <circle cx={100} cy={100} r={23} fill="currentColor" />
        <circle cx={100} cy={12} r={7} fill="currentColor" />
        <circle cx={176} cy={144} r={6.5} fill="currentColor" />
        <circle cx={24} cy={144} r={6.5} fill="currentColor" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 200 200" width={size} height={size} role="img" aria-label="Enoryx">
      <defs>
        <radialGradient id="enoryx-core" cx="35%" cy="32%" r="70%">
          <stop offset="0%" stopColor="#eaf6ff" />
          <stop offset="40%" stopColor="#7dd3fc" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </radialGradient>
        <linearGradient id="enoryx-ring" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#67e8f9" />
          <stop offset="100%" stopColor="#1e40af" />
        </linearGradient>
        <filter id="enoryx-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="3.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g fill="none" stroke="url(#enoryx-ring)" strokeWidth={3.5} filter="url(#enoryx-glow)">
        <ellipse cx={100} cy={100} rx={88} ry={40} />
        <ellipse cx={100} cy={100} rx={88} ry={40} transform="rotate(60 100 100)" />
        <ellipse cx={100} cy={100} rx={88} ry={40} transform="rotate(120 100 100)" />
      </g>

      <circle cx={100} cy={100} r={23} fill="url(#enoryx-core)" filter="url(#enoryx-glow)" />

      <g filter="url(#enoryx-glow)">
        <circle cx={100} cy={12} r={7} fill="#7dd3fc" />
        <circle cx={176} cy={144} r={6.5} fill="#38bdf8" />
        <circle cx={24} cy={144} r={6.5} fill="#38bdf8" />
      </g>
    </svg>
  );
}
