import Link from "next/link";

import { apiFetch, requireAccessToken } from "@/lib/api";
import { cellStyle, headerCellStyle } from "@/lib/formStyles";
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import { canManage as computeCanManage, type Me } from "@/lib/roles";

import { deletePlacement, validatePlacement } from "./actions";
import { PlacementEditor } from "./PlacementEditor";

type FloorPlan = {
  id: string;
  space_id: string;
  version: number;
  filename: string;
  content_type: string;
  download_url: string;
};
type Space = { id: string; site_id: string; space_type: string; code: string; name: string };
type FunctionalLocation = { id: string; site_id: string; code: string; name: string };
type Placement = {
  id: string;
  floor_plan_id: string;
  space_id: string | null;
  functional_location_id: string | null;
  point_id: string | null;
  x_ratio: number;
  y_ratio: number;
  status: string;
};
type LivePlacement = {
  id: string;
  point_value: number | null;
  point_unit: string | null;
};
type Point = { id: string; functional_location_id: string | null; space_id: string | null };
type Finding = { subject_node_id: string };

export default async function PlanEditorPage({
  params,
  searchParams,
}: {
  params: Promise<{ floorPlanId: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { floorPlanId } = await params;
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const { t } = translator;
  const locale = await getLocale();
  const { error: errorCode } = await searchParams;

  const meResponse = await apiFetch("/me", accessToken);
  const me: Me = meResponse.ok ? await meResponse.json() : { roles: [] };
  const canManage = computeCanManage(me);

  const [
    planResponse,
    placementsResponse,
    liveResponse,
    spacesResponse,
    locationsResponse,
    pointsResponse,
    openFindingsResponse,
    inProgressFindingsResponse,
  ] = await Promise.all([
    apiFetch(`/floor-plans/${floorPlanId}`, accessToken),
    apiFetch(`/floor-plans/${floorPlanId}/placements`, accessToken),
    apiFetch(`/floor-plans/${floorPlanId}/placements/live`, accessToken),
    apiFetch("/spaces", accessToken),
    apiFetch("/functional-locations", accessToken),
    apiFetch("/points", accessToken),
    apiFetch("/findings?handling_status=open", accessToken),
    apiFetch("/findings?handling_status=in_progress", accessToken),
  ]);

  if (!planResponse.ok || !canManage) {
    return (
      <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
        <Link href="/registre">← {t("common.back")}</Link>
        <h1>{t("plan_editor.title")}</h1>
        <p>{t("web.registre.access_denied")}</p>
      </main>
    );
  }

  const plan: FloorPlan = await planResponse.json();
  const placements: Placement[] = placementsResponse.ok ? await placementsResponse.json() : [];
  const live: LivePlacement[] = liveResponse.ok ? await liveResponse.json() : [];
  const allSpaces: Space[] = spacesResponse.ok ? await spacesResponse.json() : [];
  const allLocations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const points: Point[] = pointsResponse.ok ? await pointsResponse.json() : [];
  const openFindings: Finding[] = openFindingsResponse.ok ? await openFindingsResponse.json() : [];
  const inProgressFindings: Finding[] = inProgressFindingsResponse.ok
    ? await inProgressFindingsResponse.json()
    : [];

  const currentSpace = allSpaces.find((space) => space.id === plan.space_id);
  const siteId = currentSpace?.site_id;
  const siteSpaces = allSpaces.filter((space) => space.site_id === siteId);
  const siteLocations = allLocations.filter((location) => location.site_id === siteId);
  const liveById = new Map(live.map((entry) => [entry.id, entry]));
  const pointsById = new Map(points.map((point) => [point.id, point]));
  // Même règle que app/rules.py (_subject) : le constat porte sur
  // l'équipement du point, à défaut son espace, à défaut le point lui-même.
  const subjectsWithOpenFinding = new Set(
    [...openFindings, ...inProgressFindings].map((finding) => finding.subject_node_id),
  );
  function pointHasOpenFinding(pointId: string): boolean {
    const point = pointsById.get(pointId);
    if (!point) return false;
    const subject = point.functional_location_id ?? point.space_id ?? point.id;
    return subjectsWithOpenFinding.has(subject);
  }

  function targetLabel(placement: Placement): string {
    if (placement.space_id) {
      const space = siteSpaces.find((candidate) => candidate.id === placement.space_id);
      return space
        ? `${t(`space_type.${space.space_type}`)} — ${space.name}`
        : t("plan_editor.marker_unknown_target");
    }
    if (placement.functional_location_id) {
      const location = siteLocations.find(
        (candidate) => candidate.id === placement.functional_location_id,
      );
      return location ? `${location.code} — ${location.name}` : t("plan_editor.marker_unknown_target");
    }
    return t("plan_editor.marker_point_target");
  }

  const isImage = plan.content_type === "image/png" || plan.content_type === "image/jpeg";
  const markers = placements.map((placement) => {
    const value = liveById.get(placement.id);
    const label = targetLabel(placement);
    const status = t(`plan_editor.marker_status_${placement.status}`);
    const valueSuffix =
      value && value.point_value !== null
        ? ` — ${t("plan_editor.live_value_label")}: ${value.point_value}${value.point_unit ?? ""}`
        : "";
    const warning = placement.point_id !== null && pointHasOpenFinding(placement.point_id);
    const warningSuffix = warning ? ` — ${t("plan_editor.marker_open_finding")}` : "";
    return {
      id: placement.id,
      x: placement.x_ratio,
      y: placement.y_ratio,
      color: placement.status === "validated" ? "#16a34a" : "#9ca3af",
      warning,
      title: `${label} — ${status}${valueSuffix}${warningSuffix}`,
    };
  });

  const error = errorCode
    ? errorMessage(locale, errorCode) ?? t("web.registre.creation_failed")
    : null;

  return (
    <main style={{ maxWidth: 900, margin: "40px auto", padding: "0 16px" }}>
      <Link href="/registre">← {t("common.back")}</Link>
      <h1>{t("plan_editor.title")}</h1>
      <p>
        {t("plan_editor.plan_label")} : {plan.filename} —{" "}
        {t("plan_editor.version_label", { version: plan.version })}
      </p>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}

      {!isImage ? (
        <p>{t("plan_editor.unsupported_content_type")}</p>
      ) : (
        <PlacementEditor
          floorPlanId={plan.id}
          imageUrl={plan.download_url}
          markers={markers}
          spaceOptions={siteSpaces.map((space) => ({
            id: space.id,
            label: `${t(`space_type.${space.space_type}`)} — ${space.name}`,
          }))}
          locationOptions={siteLocations.map((location) => ({
            id: location.id,
            label: `${location.code} — ${location.name}`,
          }))}
          labels={{
            clickHint: t("plan_editor.click_hint"),
            noCoordinatesSelected: t("plan_editor.no_coordinates_selected"),
            coordinatesSelected: t("plan_editor.coordinates_selected"),
            targetTypeLabel: t("plan_editor.target_type_label"),
            targetTypeSpace: t("plan_editor.target_type_space"),
            targetTypeFunctionalLocation: t("plan_editor.target_type_functional_location"),
            targetIdLabel: t("plan_editor.target_id_label"),
            addMarker: t("plan_editor.add_marker"),
          }}
        />
      )}

      <h2 style={{ marginTop: 32 }}>{t("plan_editor.markers_title")}</h2>
      {placements.length === 0 ? (
        <p>{t("plan_editor.markers_none")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={headerCellStyle}>{t("web.dashboard.name")}</th>
              <th style={headerCellStyle} />
              <th style={headerCellStyle} />
            </tr>
          </thead>
          <tbody>
            {placements.map((placement) => (
              <tr key={placement.id}>
                <td style={cellStyle}>
                  {targetLabel(placement)} —{" "}
                  {t(`plan_editor.marker_status_${placement.status}`)}
                  {placement.point_id !== null && pointHasOpenFinding(placement.point_id) && (
                    <span style={{ color: "#dc2626" }}> — {t("plan_editor.marker_open_finding")}</span>
                  )}
                </td>
                <td style={cellStyle}>
                  {placement.status === "proposed" && (
                    <form action={validatePlacement} style={{ display: "inline" }}>
                      <input type="hidden" name="floor_plan_id" value={plan.id} />
                      <input type="hidden" name="placement_id" value={placement.id} />
                      <button type="submit">{t("plan_editor.marker_validate")}</button>
                    </form>
                  )}
                </td>
                <td style={cellStyle}>
                  <form action={deletePlacement} style={{ display: "inline" }}>
                    <input type="hidden" name="floor_plan_id" value={plan.id} />
                    <input type="hidden" name="placement_id" value={placement.id} />
                    <button type="submit">{t("plan_editor.marker_delete")}</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
