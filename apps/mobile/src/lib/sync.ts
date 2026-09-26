import {
  deletePendingIntervention,
  listPendingInterventions,
  markClosureSent,
  markInterventionCreated,
  markPhotoUploaded,
  replaceFunctionalLocationsCache,
  type PendingIntervention,
} from "./db";

export type SyncResult = {
  synced: number;
  failed: number;
};

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

/**
 * Rafraîchit la liste des positions fonctionnelles (équipements) disponibles
 * hors ligne, pour que le technicien puisse choisir sur quel équipement il
 * intervient même sans réseau au moment de créer l'intervention.
 */
export async function refreshFunctionalLocationsCache(
  apiUrl: string,
  accessToken: string,
): Promise<void> {
  const response = await fetch(`${apiUrl}/functional-locations`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    throw new Error(`liste des équipements : ${response.status}`);
  }
  const locations = await response.json();
  await replaceFunctionalLocationsCache(
    locations.map((location: { id: string; code: string; name: string }) => ({
      id: location.id,
      code: location.code,
      name: location.name,
    })),
  );
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
    throw new Error(`url d'envoi photo : ${uploadUrlResponse.status}`);
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
    throw new Error(`envoi photo : ${putResponse.status}`);
  }

  const confirmResponse = await fetch(`${apiUrl}/interventions/${interventionId}/photos`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ object_key: objectKey, taken_at: row.started_at, client_ref: row.id }),
  });
  if (!confirmResponse.ok) {
    throw new Error(`confirmation photo : ${confirmResponse.status}`);
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
