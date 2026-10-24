/**
 * Synchronisation incrémentale par pages (consolidation V5 du 21/10/2026).
 *
 * Avant : chaque synchronisation retéléchargeait toutes les interventions (35 Mo
 * à 100 000 lignes) et tous les équipements. Maintenant : le téléphone garde un
 * point de reprise (« curseur ») par flux et ne demande que la suite, par pages
 * de quelques dizaines de lignes (voir app/sync_feed.py côté serveur).
 *
 * Propriétés recherchées, prouvées par syncFeed.test.ts sur un vrai SQLite :
 * - une page et son curseur sont enregistrés dans UNE SEULE transaction locale :
 *   un arrêt brutal (réseau perdu, application tuée) ne laisse jamais un curseur
 *   en avance sur les lignes, donc aucune ligne perdue ;
 * - le serveur peut renvoyer une ligne déjà reçue (fenêtre de recouvrement) ou le
 *   même page deux fois : l'application l'ignore par son identifiant, donc aucun
 *   doublon ;
 * - un parcours interrompu reprend à la page suivante, jamais au début ;
 * - le travail par synchronisation est borné (`maxPages`) : sur une connexion
 *   faible, on avance par morceaux plutôt que de tout tenter d'un coup.
 */

export type FeedName = "interventions" | "functional_locations";

export type FeedPage<T> = {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
};

export type FeedStore<T> = {
  getCursor(feed: FeedName): Promise<string | null>;
  /** Applique les lignes ET enregistre le curseur dans la même transaction. */
  applyPage(feed: FeedName, items: T[], cursor: string | null, syncedAt: string): Promise<void>;
  /** Oublie le point de reprise : le prochain parcours repart du début. */
  resetCursor(feed: FeedName): Promise<void>;
};

export type PullResult = {
  pages: number;
  items: number;
  /** Faux si le plafond de pages a été atteint : la suite viendra à la prochaine synchronisation. */
  complete: boolean;
};

/** Le serveur ne reconnaît plus le curseur (code SYNC_CURSOR_INVALID). */
export class CursorRejectedError extends Error {
  constructor() {
    super("curseur de synchronisation refusé par le serveur");
    this.name = "CursorRejectedError";
  }
}

export const DEFAULT_MAX_PAGES = 40;

export async function pullFeed<T>(args: {
  feed: FeedName;
  store: FeedStore<T>;
  fetchPage: (after: string | null) => Promise<FeedPage<T>>;
  maxPages?: number;
  now?: () => string;
}): Promise<PullResult> {
  const { feed, store, fetchPage } = args;
  const maxPages = args.maxPages ?? DEFAULT_MAX_PAGES;
  const now = args.now ?? (() => new Date().toISOString());

  try {
    return await pull(feed, store, fetchPage, maxPages, now);
  } catch (error) {
    if (!(error instanceof CursorRejectedError)) throw error;
    // Point de reprise inutilisable (base du serveur restaurée, format changé) :
    // on repart du début. Les lignes déjà présentes sont simplement mises à jour.
    await store.resetCursor(feed);
    return pull(feed, store, fetchPage, maxPages, now);
  }
}

async function pull<T>(
  feed: FeedName,
  store: FeedStore<T>,
  fetchPage: (after: string | null) => Promise<FeedPage<T>>,
  maxPages: number,
  now: () => string,
): Promise<PullResult> {
  let cursor = await store.getCursor(feed);
  let pages = 0;
  let items = 0;

  while (pages < maxPages) {
    const page = await fetchPage(cursor);
    if (page.has_more && (page.next_cursor === null || page.next_cursor === cursor)) {
      // Un serveur qui annonce une suite sans faire avancer le curseur nous
      // ferait boucler sans fin : on s'arrête et on le signale.
      throw new Error("la synchronisation n'avance plus (curseur identique)");
    }
    await store.applyPage(feed, page.items, page.next_cursor ?? cursor, now());
    pages += 1;
    items += page.items.length;
    cursor = page.next_cursor ?? cursor;
    if (!page.has_more) {
      return { pages, items, complete: true };
    }
  }
  return { pages, items, complete: false };
}
