/**
 * Symbole de marque : noyau = intelligence, anneaux orbitaux = supervision
 * continue, nœuds = actifs connectés. Provisoire (directive de Mohamed du
 * 30/09/2026, section 2) : aucun identifiant de code n'est couplé au nom de
 * marque, pour qu'un futur symbole puisse le remplacer sans toucher aux
 * pages qui l'utilisent — seul ce fichier changerait. `label` porte le nom
 * affiché (passé par l'appelant via `common.app_name`), jamais écrit en dur
 * ici. Inline (pas une balise <img>) pour que `variant="mono"` hérite la
 * couleur du texte environnant via `currentColor` — premier composant
 * partagé de `apps/web/src/components/` (ADR 014, Design System commun).
 */
export function BrandMark({
  variant = "glow",
  size = 32,
  label = "",
}: {
  variant?: "glow" | "mono";
  size?: number;
  label?: string;
}) {
  if (variant === "mono") {
    return (
      <svg viewBox="0 0 200 200" width={size} height={size} role="img" aria-label={label}>
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
    <svg viewBox="0 0 200 200" width={size} height={size} role="img" aria-label={label}>
      <defs>
        <radialGradient id="brand-mark-core" cx="35%" cy="32%" r="70%">
          <stop offset="0%" stopColor="#eaf6ff" />
          <stop offset="40%" stopColor="#7dd3fc" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </radialGradient>
        <linearGradient id="brand-mark-ring" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#67e8f9" />
          <stop offset="100%" stopColor="#1e40af" />
        </linearGradient>
        <filter id="brand-mark-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="3.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g fill="none" stroke="url(#brand-mark-ring)" strokeWidth={3.5} filter="url(#brand-mark-glow)">
        <ellipse cx={100} cy={100} rx={88} ry={40} />
        <ellipse cx={100} cy={100} rx={88} ry={40} transform="rotate(60 100 100)" />
        <ellipse cx={100} cy={100} rx={88} ry={40} transform="rotate(120 100 100)" />
      </g>

      <circle cx={100} cy={100} r={23} fill="url(#brand-mark-core)" filter="url(#brand-mark-glow)" />

      <g filter="url(#brand-mark-glow)">
        <circle cx={100} cy={12} r={7} fill="#7dd3fc" />
        <circle cx={176} cy={144} r={6.5} fill="#38bdf8" />
        <circle cx={24} cy={144} r={6.5} fill="#38bdf8" />
      </g>
    </svg>
  );
}
