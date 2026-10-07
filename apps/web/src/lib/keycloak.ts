/**
 * Dérive l'URL de la console d'administration Keycloak depuis l'adresse
 * OIDC déjà configurée (OIDC_ISSUER, forme `<base>/realms/<realm>`) : ne
 * demande ni compte de service ni secret supplémentaire (voir la page
 * Users & Access, section 36 point 11 — un appel à l'API d'administration
 * Keycloak exigerait l'un ou l'autre, voir docs/spec/feature-benchmark-matrix.md).
 * Renvoie `null` si l'adresse ne suit pas ce format attendu.
 */
export function keycloakAdminConsoleUrl(oidcIssuer: string): string | null {
  const marker = "/realms/";
  const index = oidcIssuer.indexOf(marker);
  if (index === -1) {
    return null;
  }
  const base = oidcIssuer.slice(0, index);
  const realm = oidcIssuer.slice(index + marker.length).replace(/\/+$/, "");
  if (!base || !realm) {
    return null;
  }
  return `${base}/admin/master/console/#/${realm}/users`;
}
