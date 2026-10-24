/**
 * Index des équipements pour retrouver le nom d'un équipement à partir de son identifiant.
 *
 * `GET /functional-locations` n'envoie pas les équipements archivés par défaut, alors que
 * les alarmes, constats, ordres de travail, mesures et consommations qui les concernent
 * restent visibles (une alarme ouverte n'est jamais masquée parce que son équipement a été
 * archivé, par exemple avec son site). Sans l'équipement archivé dans l'index, ces lignes
 * affichaient « — » sans dire de quel équipement il s'agit.
 *
 * Un écran demande donc `?include_archived=true` et passe la liste ici : `byId` retrouve tous
 * les équipements, `active` ne garde que ceux qui comptent dans les décomptes et les menus.
 */
export type LocationRecord = { id: string; archived_at?: string | null };

export function isArchivedLocation(location: LocationRecord): boolean {
  return Boolean(location.archived_at);
}

export function indexLocations<T extends LocationRecord>(
  all: T[],
): { active: T[]; byId: Map<string, T> } {
  return {
    active: all.filter((location) => !isArchivedLocation(location)),
    byId: new Map(all.map((location) => [location.id, location])),
  };
}
