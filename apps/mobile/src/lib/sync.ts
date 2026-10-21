import {
  deletePendingIntervention,
  getFeedStore,
  listPendingInterventions,
  markClosureSent,
  markFgasSent,
  markInterventionCreated,
  markPhotoUploaded,
  type PendingIntervention,
} from "./db";
import {
  CursorRejectedError,
  pullFeed,
  type FeedName,
  type FeedPage,
  type PullResult,
} from "./syncFeed";
import type { FeedItem } from "./syncStore";

export type SyncResult = {
  synced: number;
  failed: number;
  /**
   * Vrai si la récupération des données du serveur n'est pas allée à son terme
   * (plafond de pages atteint, ou erreur de réseau) : la suite viendra à la
   * prochaine synchronisation, au point où elle s'est arrêtée.
   */
  incomplete?: boolean;
};

/** Fenêtre d'historique chargée au premier parcours : le téléphone n'a pas besoin des années passées. */
export const HISTORY_WINDOW_DAYS = 30;

let inFlightSync: Promise<SyncResult> | null = null;

/**
 * Point d'entrée unique pour synchroniser (interventions en attente puis
 * cache des équipements). La création d'une intervention et le retour du
 * réseau peuvent chacun déclencher une synchronisation à quelques
 * millisecondes d'écart ; deux synchronisations en même temps écrivent
 * toutes les deux dans la base locale, et SQLite n'autorise qu'un seul
 * écrivain à la fois même en mode WAL — la seconde écriture échoue alors
 * avec "database is locked". Un appel pendant qu'une synchronisation est
 * déjà en cours attend simplement son résultat plutôt que d'en démarrer une
 * seconde.
 */
export function synchronize(apiUrl: string, accessToken: string): Promise<SyncResult> {
  if (!inFlightSync) {
    inFlightSync = runSynchronize(apiUrl, accessToken).finally(() => {
      inFlightSync = null;
    });
  }
  return inFlightSync;
}

async function runSynchronize(apiUrl: string, accessToken: string): Promise<SyncResult> {
  const result = await syncPendingInterventions(apiUrl, accessToken);
  // Les deux flux sont indépendants : l'échec de l'un n'empêche pas l'autre, et
  // chacun reprend à son propre point de reprise à la synchronisation suivante.
  let incomplete = false;
  for (const feed of FEEDS) {
    const pulled = await pullFromServer(apiUrl, accessToken, feed).catch((error) => {
      // eslint-disable-next-line no-console -- diagnostic terrain (voir plus bas).
      console.error(`Échec de la synchronisation du flux ${feed}`, error);
      return null;
    });
    if (!pulled?.complete) incomplete = true;
  }
  return { ...result, incomplete };
}

const FEEDS: FeedName[] = ["functional_locations", "interventions"];

const FEED_PATH: Record<FeedName, string> = {
  functional_locations: "/sync/functional-locations",
  interventions: "/sync/interventions",
};

/** Pages courtes : sur une connexion faible, une coupure ne perd que la page en cours. */
const FEED_PAGE_SIZE = 100;
/** Une requête qui n'aboutit pas dans ce délai est abandonnée (sinon la synchronisation resterait bloquée). */
const FEED_REQUEST_TIMEOUT_MS = 20_000;

/**
 * Récupère ce qui a changé sur le serveur depuis le dernier point de reprise
 * (équipements, puis historique des interventions), par pages. Remplace le
 * téléchargement intégral de ces listes à chaque synchronisation.
 */
export async function pullFromServer(
  apiUrl: string,
  accessToken: string,
  feed: FeedName,
): Promise<PullResult> {
  return pullFeed<FeedItem>({
    feed,
    store: await getFeedStore(),
    fetchPage: (after) => fetchFeedPage(apiUrl, accessToken, feed, after),
  });
}

async function fetchFeedPage(
  apiUrl: string,
  accessToken: string,
  feed: FeedName,
  after: string | null,
): Promise<FeedPage<FeedItem>> {
  // Premier parcours de l'historique : seulement la fenêtre récente, pas les années passées.
  const since =
    !after && feed === "interventions"
      ? `&since=${encodeURIComponent(
          new Date(Date.now() - HISTORY_WINDOW_DAYS * 86_400_000).toISOString(),
        )}`
      : "";
  const query = `limit=${FEED_PAGE_SIZE}${after ? `&after=${encodeURIComponent(after)}` : since}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FEED_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${apiUrl}${FEED_PATH[feed]}?${query}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 400) {
        const body = await response.json().catch(() => null);
        if (body?.code === "SYNC_CURSOR_INVALID") throw new CursorRejectedError();
      }
      throw new Error(`flux ${feed} : ${response.status}`);
    }
    return (await response.json()) as FeedPage<FeedItem>;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Envoie les interventions créées hors ligne vers l'API, dans l'ordre où
 * elles ont été créées. Chaque étape (créer l'intervention, puis la photo)
 * met à jour la ligne locale au fur et à mesure : si l'envoi s'interrompt
 * en cours de route (réseau perdu à nouveau), reprendre plus tard ne recrée
 * jamais une intervention en double (voir ADR 010).
 */
export async function syncPendingInterventions(
  apiUrl: string,
  accessToken: string,
): Promise<SyncResult> {
  const rows = await listPendingInterventions();
  let synced = 0;
  let failed = 0;

  for (const row of rows) {
    try {
      const serverId = await ensureInterventionCreated(apiUrl, accessToken, row);
      if (!row.photo_uploaded) {
        await uploadPhoto(apiUrl, accessToken, serverId, row);
        await markPhotoUploaded(row.id);
      }
      if (row.closure && !row.closure_sent) {
        await sendClosure(apiUrl, accessToken, serverId, row.closure);
        await markClosureSent(row.id);
      }
      if (row.fgas && !row.fgas_sent) {
        await sendFgas(apiUrl, accessToken, serverId, row.fgas);
        await markFgasSent(row.id);
      }
      await deletePendingIntervention(row.id);
      synced += 1;
    } catch (error) {
      // eslint-disable-next-line no-console -- diagnostic terrain : sans ce
      // log, un échec de synchronisation reste invisible (voir ADR 013).
      console.error(`Échec de synchronisation de l'intervention ${row.id}`, error);
      failed += 1;
    }
  }

  return { synced, failed };
}

async function ensureInterventionCreated(
  apiUrl: string,
  accessToken: string,
  row: PendingIntervention,
): Promise<string> {
  if (row.server_id) {
    return row.server_id;
  }

  const response = await fetch(`${apiUrl}/interventions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({
      intervention_type: row.intervention_type,
      summary: row.summary,
      checklist: JSON.parse(row.checklist),
      started_at: row.started_at,
      functional_location_id: row.functional_location_id,
      work_order_id: row.work_order_id,
      // Si la réponse se perd après la création, le renvoi porte la même
      // référence : le serveur rend l'intervention déjà créée, sans doublon.
      client_ref: row.id,
    }),
  });
  if (!response.ok) {
    throw new Error(`création intervention : ${response.status}`);
  }
  const data = await response.json();
  await markInterventionCreated(row.id, data.id);
  return data.id as string;
}

async function uploadPhoto(
  apiUrl: string,
  accessToken: string,
  interventionId: string,
  row: PendingIntervention,
): Promise<void> {
  const uploadUrlResponse = await fetch(
    `${apiUrl}/interventions/${interventionId}/photos/upload-url`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ filename: `${row.id}.jpg`, content_type: "image/jpeg" }),
    },
  );
  if (!uploadUrlResponse.ok) {
    throw new Error(
      `url d'envoi photo : ${uploadUrlResponse.status} ${await uploadUrlResponse.text()}`,
    );
  }
  const { upload_url: uploadUrl, object_key: objectKey } = await uploadUrlResponse.json();

  const fileResponse = await fetch(row.photo_path);
  const blob = await fileResponse.blob();
  const putResponse = await fetch(uploadUrl, {
    method: "PUT",
    body: blob,
    headers: { "Content-Type": "image/jpeg" },
  });
  if (!putResponse.ok) {
    // Le corps de la réponse (pas seulement le code HTTP) contient le motif
    // exact renvoyé par le stockage (R2) : signature invalide, identifiants,
    // bucket... indispensable pour diagnostiquer un 403 depuis le terrain.
    throw new Error(`envoi photo : ${putResponse.status} ${await putResponse.text()}`);
  }

  const confirmResponse = await fetch(`${apiUrl}/interventions/${interventionId}/photos`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ object_key: objectKey, taken_at: row.started_at, client_ref: row.id }),
  });
  if (!confirmResponse.ok) {
    throw new Error(
      `confirmation photo : ${confirmResponse.status} ${await confirmResponse.text()}`,
    );
  }
}

/**
 * Clôture structurée, envoyée après la photo. Rejouable : si la réponse s'est
 * perdue, le serveur rend la clôture déjà enregistrée (200) au lieu de la
 * dupliquer ; un contenu différent est refusé (409) et la ligne reste en
 * attente, visible, plutôt que d'être perdue.
 */
async function sendClosure(
  apiUrl: string,
  accessToken: string,
  interventionId: string,
  closure: string,
): Promise<void> {
  const response = await fetch(`${apiUrl}/interventions/${interventionId}/closure`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: closure,
  });
  if (!response.ok) {
    throw new Error(`clôture : ${response.status}`);
  }
}

/**
 * Fiche F-Gas (CERFA 15497*04), envoyée après la clôture. Rejouable comme
 * la clôture : une réponse perdue renvoie la fiche déjà enregistrée (200)
 * plutôt que de la dupliquer ; un contenu différent est refusé (409) et la
 * ligne reste en attente, visible.
 */
async function sendFgas(
  apiUrl: string,
  accessToken: string,
  interventionId: string,
  fgas: string,
): Promise<void> {
  const response = await fetch(`${apiUrl}/interventions/${interventionId}/fgas`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: fgas,
  });
  if (!response.ok) {
    throw new Error(`fiche F-Gas : ${response.status}`);
  }
}
