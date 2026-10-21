/**
 * Pagination des listes qui grossissent sans fin (consolidation V5 du
 * 21/10/2026). Le serveur pagine déjà (`limit`, `offset`, en-tête
 * `X-Total-Count`, app/pagination.py) ; ce module en tire la fenêtre affichée
 * (« 51–100 sur 230 ») et les liens précédent/suivant.
 */

export const DEFAULT_PAGE_SIZE = 50;

/** Numéro de page lu dans l'adresse : tout ce qui n'est pas un entier ≥ 1 donne la page 1. */
export function parsePage(raw: string | undefined): number {
  const page = Number(raw);
  return Number.isInteger(page) && page >= 1 ? page : 1;
}

/** Total annoncé par le serveur, ou null s'il ne l'a pas fourni (jamais un faux zéro). */
export function totalCount(response: { headers: { get(name: string): string | null } }): number | null {
  const header = response.headers.get("X-Total-Count");
  if (header === null) return null;
  const total = Number(header);
  return Number.isInteger(total) && total >= 0 ? total : null;
}

export function pageOffset(page: number, pageSize: number = DEFAULT_PAGE_SIZE): number {
  return (page - 1) * pageSize;
}

export type PageWindow = {
  page: number;
  totalPages: number;
  from: number;
  to: number;
  total: number;
  hasPrevious: boolean;
  hasNext: boolean;
};

export function pageWindow(args: {
  page: number;
  total: number;
  returned: number;
  pageSize?: number;
}): PageWindow {
  const pageSize = args.pageSize ?? DEFAULT_PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(args.total / pageSize));
  const start = pageOffset(args.page, pageSize);
  return {
    page: args.page,
    totalPages,
    from: args.returned === 0 ? 0 : start + 1,
    to: start + args.returned,
    total: args.total,
    hasPrevious: args.page > 1,
    hasNext: args.page < totalPages,
  };
}

/** Dernière page existante pour ce total, vers laquelle ramener une adresse trop loin. */
export function lastPage(total: number, pageSize: number = DEFAULT_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / pageSize));
}
