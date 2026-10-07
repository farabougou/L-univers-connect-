/**
 * Identité de la personne connectée (GET /me), partagée par l'écran Profil,
 * le tiroir de navigation (affichage conditionnel d'« Ajouter un site ») et
 * le tableau de bord Accueil — un seul appel réseau factorisé plutôt que
 * trois copies de la même requête.
 */
export type Me = {
  sub: string;
  tenant_id: string;
  tenant_name: string | null;
  roles: string[];
};

export async function fetchMe(apiUrl: string, accessToken: string): Promise<Me | null> {
  const response = await fetch(`${apiUrl}/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return response.ok ? ((await response.json()) as Me) : null;
}
