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
