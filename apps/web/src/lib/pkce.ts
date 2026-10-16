import { createHash, randomBytes } from "node:crypto";

/**
 * Génère une paire PKCE (voir infra/README.md : le web utilise le même flux
 * "Authorization Code + PKCE" que l'application mobile, jamais de mot de
 * passe géré directement par ce serveur).
 */
export function generatePkcePair(): { codeVerifier: string; codeChallenge: string } {
  const codeVerifier = randomBytes(32).toString("base64url");
  const codeChallenge = createHash("sha256").update(codeVerifier).digest("base64url");
  return { codeVerifier, codeChallenge };
}

/**
 * Valeur aléatoire imprévisible renvoyée telle quelle par Keycloak, comparée
 * au retour pour se protéger d'une CSRF de connexion (un attaquant qui
 * pousserait sa propre autorisation dans le navigateur de la victime) — une
 * protection standard OAuth, complémentaire à PKCE, pas remplacée par lui.
 */
export function generateState(): string {
  return randomBytes(16).toString("base64url");
}
