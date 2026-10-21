import { listCachedFunctionalLocations } from "./db";

export type EquipmentLabel = { id: string; code: string; name: string };

/**
 * Libellés des équipements (code, nom) pour les écrans qui affichent autre
 * chose que l'équipement lui-même (alertes, énergie, activité récente).
 *
 * Avant la consolidation V5 (21/10/2026), chacun de ces écrans retéléchargeait
 * toute la liste des équipements à chaque ouverture. Le téléphone la tient
 * maintenant à jour ligne à ligne (src/lib/syncFeed.ts) : on la lit sur place.
 * Le réseau n'est utilisé que tant que cette liste locale est vide (tout premier
 * lancement, avant la première synchronisation).
 */
export async function loadEquipmentLabels(
  apiUrl: string,
  accessToken: string,
): Promise<EquipmentLabel[]> {
  const cached = await listCachedFunctionalLocations().catch(() => []);
  if (cached.length > 0) return cached;
  const response = await fetch(`${apiUrl}/functional-locations`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  }).catch(() => null);
  return response?.ok ? ((await response.json()) as EquipmentLabel[]) : [];
}
