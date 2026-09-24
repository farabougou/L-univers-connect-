/**
 * Rôles de gestion du registre (créer/modifier un site, un équipement, une
 * règle...), identiques aux rôles `_MANAGE_ROLES` / `_MANAGE_REGISTRY_ROLES`
 * côté API : dupliqués ici uniquement parce que le navigateur ne peut pas
 * lire le code Python, jamais comme une deuxième source de vérité — l'API
 * revérifie toujours elle-même chaque action.
 */
export const MANAGE_ROLES = ["responsable_exploitation", "admin_tenant"];

/**
 * Rôles autorisés à envoyer une commande (appareil explicitement simulé
 * uniquement — voir CLAUDE.md, exception à la règle non négociable 1),
 * identiques à `_COMMAND_ROLES` dans app/routers/commands.py. Un technicien
 * peut opérer un relais déjà configuré sans pouvoir gérer le registre :
 * volontairement distinct de `MANAGE_ROLES`.
 */
export const COMMAND_ROLES = ["technicien", "responsable_exploitation", "admin_tenant"];

export type Me = { roles: string[] };

export function canManage(me: Me): boolean {
  return me.roles.some((role) => MANAGE_ROLES.includes(role));
}

export function canSendCommand(me: Me): boolean {
  return me.roles.some((role) => COMMAND_ROLES.includes(role));
}
