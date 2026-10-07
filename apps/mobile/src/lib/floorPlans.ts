/**
 * Plans 2D du portefeuille, lecture seule côté terrain — écran
 * app/plans.tsx. Même endpoint bulk que la page web Spatial/BIM
 * (apps/web/src/app/plans/page.tsx, GET /floor-plans/portfolio,
 * `app/floor_plans.py::list_portfolio_floor_plans`) : dernière version de
 * chaque plan, avec le site et l'espace visés. L'éditeur de placements
 * (poser un équipement sur le plan) reste réservé au web
 * (`/registre/plans/[floorPlanId]`) — ce que ce fichier ne reproduit pas,
 * par décision de périmètre (06/10/2026) : un technicien consulte le plan
 * déjà posé, il ne le repositionne pas depuis le terrain.
 */

export type PortfolioFloorPlan = {
  id: string;
  siteId: string;
  siteName: string;
  spaceId: string;
  spaceCode: string;
  spaceName: string;
  version: number;
  filename: string;
  contentType: string;
  downloadUrl: string;
  uploadedAt: string;
};

type RawPortfolioFloorPlan = {
  id: string;
  space_id: string;
  space_code: string;
  space_name: string;
  site_id: string;
  site_name: string;
  version: number;
  filename: string;
  content_type: string;
  download_url: string;
  uploaded_by: string;
  uploaded_at: string;
  validated_placement_count: number;
};

export async function fetchPortfolioFloorPlans(
  apiUrl: string,
  accessToken: string,
): Promise<PortfolioFloorPlan[]> {
  const response = await fetch(`${apiUrl}/floor-plans/portfolio`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) return [];
  const rows = (await response.json()) as RawPortfolioFloorPlan[];
  return rows.map((row) => ({
    id: row.id,
    siteId: row.site_id,
    siteName: row.site_name,
    spaceId: row.space_id,
    spaceCode: row.space_code,
    spaceName: row.space_name,
    version: row.version,
    filename: row.filename,
    contentType: row.content_type,
    downloadUrl: row.download_url,
    uploadedAt: row.uploaded_at,
  }));
}
