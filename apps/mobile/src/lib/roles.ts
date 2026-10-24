/**
 * Un identifiant technique de rôle (`admin_tenant`) n'est jamais montré tel
 * quel à une personne (directive de Mohamed du 30/09/2026, section 3) : le
 * libellé humain vient du catalogue `role.*`, jamais écrit en dur ici. Les
 * autorisations réelles restent imposées côté serveur — ceci n'est qu'un
 * affichage. Même fonction que `apps/web/src/lib/roles.ts::roleLabels`,
 * dupliquée ici car les deux applications ne partagent pas leur code, comme
 * les autres listes de rôles du projet.
 */
export function roleLabels(roles: string[], t: (key: string) => string): string {
  return roles.map((role) => t(`role.${role}`)).join(", ");
}

/**
 * Rôles de gestion du registre (créer un site...), identiques à
 * `_MANAGE_REGISTRY_ROLES` (services/api/app/routers/assets.py) et à
 * `MANAGE_ROLES` côté web (apps/web/src/lib/roles.ts) — dupliqué ici
 * uniquement parce que le téléphone ne peut pas lire le code Python, jamais
 * comme une deuxième source de vérité : l'API revérifie toujours chaque
 * action. N'affiche "Ajouter un site" (06/10/2026) que pour ces rôles,
 * plutôt que de laisser un technicien ouvrir un formulaire qui échouera.
 */
export const MANAGE_ROLES = ["responsable_exploitation", "admin_tenant"];

export function canManage(roles: string[]): boolean {
  return roles.some((role) => MANAGE_ROLES.includes(role));
}
