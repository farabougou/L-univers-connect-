/**
 * Analyse du code d'une étiquette (saisi à la main ou décodé d'un QR) —
 * même règle que l'application mobile (apps/mobile/src/lib/passport.ts),
 * dupliquée ici car web et mobile ne partagent pas de code. Le contenu
 * d'un QR imprimé est toujours `paios:tag:<code>` (voir `renderTagQr`
 * côté création) ; un code tapé à la main n'a pas ce préfixe.
 */

export const QR_PREFIX = "paios:tag:";

// Même alphabet que secrets.token_urlsafe côté serveur.
const CODE_PATTERN = /^[A-Za-z0-9_-]{8,64}$/;

export function parseTagCode(input: string): string | null {
  let code = input.trim();
  if (code.startsWith(QR_PREFIX)) {
    code = code.slice(QR_PREFIX.length);
  }
  return CODE_PATTERN.test(code) ? code : null;
}
