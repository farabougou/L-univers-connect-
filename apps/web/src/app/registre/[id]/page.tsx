import Link from "next/link";
import QRCode from "qrcode";

import { apiFetch, requireAccessToken } from "@/lib/api";
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import { type EquipmentStatus, type Passport, type PassportUnit, statusMessage } from "@/lib/passport";
import { type Locale, formatDate, formatDateTime, formatNumber } from "@/i18n/translator";

import {
  acknowledgeSignal,
  activateRule,
  changeLifecycleState,
  clearAlarm,
  confirmFinding,
  createDivergenceRule,
  createTagForEquipment,
  createThresholdRule,
  createWorkOrderForEquipment,
  declareDesiredState,
  endDesiredState,
  retireRule,
  revokeTag,
  setAssetCode,
  setHandling,
  setProperty,
} from "./actions";

type RuleContent = {
  kind: "threshold" | "desired_state_divergence";
  severity: string;
  title: string;
  operator?: string;
  threshold?: number;
  tolerance?: number;
};
type ConfigVersion = {
  id: string;
  version: number;
  status: string;
  content: RuleContent;
};

const PROPERTY_SOURCES = ["nameplate", "document", "measurement", "manual"];
// Même vocabulaire fermé que app/properties.py (PROPERTIES) : une propriété
// technique ne se saisit jamais en texte libre (F-Gas, plaques normalisées).
const PROPERTY_KEYS = [
  "refrigerant_type",
  "refrigerant_charge",
  "nominal_cooling_capacity",
  "nominal_heating_capacity",
  "nominal_electrical_power",
  "manufacture_year",
];

// Même transitions que app/lifecycle.py, sans les états imposés par
// l'affectation (installed/removed) : ceux-là ne se déclarent pas à la main.
const LIFECYCLE_TRANSITIONS: Record<string, string[]> = {
  planned: ["ordered", "in_stock"],
  ordered: ["in_stock"],
  in_stock: ["decommissioned", "disposed"],
  installed: ["commissioned"],
  commissioned: ["in_service"],
  in_service: ["out_of_service"],
  out_of_service: ["in_service"],
  removed: ["in_stock", "decommissioned"],
  decommissioned: ["disposed"],
  disposed: [],
};

type DesiredState = {
  id: string;
  point_id: string;
  value: number;
  valid_from: string;
  valid_to: string | null;
};

type Me = { roles: string[] };

const MANAGE_ROLES = ["responsable_exploitation", "admin_tenant"];
const WORK_ORDER_TYPES = ["corrective", "preventive", "predictive", "inspection"];
const WORK_ORDER_PRIORITIES = ["low", "medium", "high", "urgent"];

const sectionStyle = { borderTop: "1px solid #eee", paddingTop: 12, marginTop: 16 };
const sectionTitleStyle = { fontSize: 16, fontWeight: 600 as const, marginBottom: 8 };
const mutedStyle = { color: "#666" };
const strongStyle = { fontWeight: 600 as const };
const signalActionsStyle = { display: "flex", gap: 8, marginTop: 4 };
const fieldStyle = { display: "block", width: "100%", padding: 8, marginTop: 4 };
const labelStyle = { display: "block", marginTop: 12 };
const submitStyle = {
  marginTop: 16,
  padding: "10px 20px",
  background: "#2563eb",
  color: "white",
  border: "none",
  borderRadius: 8,
};
const HANDLING_OPEN = ["open", "in_progress"];

export default async function EquipmentPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { id } = await params;
  const { error: errorCode } = await searchParams;
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const locale = await getLocale();
  const { t } = translator;
  const error = errorCode
    ? (errorMessage(translator.locale, errorCode) ?? t("web.registre.creation_failed"))
    : null;

  const [response, meResponse] = await Promise.all([
    apiFetch(`/graph/nodes/${id}/passport`, accessToken),
    apiFetch("/me", accessToken),
  ]);
  const me: Me = meResponse.ok ? await meResponse.json() : { roles: [] };
  const canManage = me.roles.some((role) => MANAGE_ROLES.includes(role));
  if (!response.ok) {
    return (
      <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
        <Link href="/registre">← {t("common.back")}</Link>
        <p>{t("web.registre.equipment_not_found")}</p>
      </main>
    );
  }
  // Contrairement à /tags/{code} (utilisé par le mobile), cette route
  // renvoie directement l'objet passeport, sans enveloppe.
  const passport: Passport = await response.json();
  const unit = passport.physical_unit ?? passport.current_unit ?? null;
  const timeZone = passport.site?.timezone ?? null;
  const alarms = passport.open_alarms ?? [];
  const points = passport.points ?? [];
  const activeTag = passport.tags?.find((tag) => tag.status === "active") ?? null;
  const tagSvg = activeTag
    ? await QRCode.toString(activeTag.payload, { type: "svg", margin: 1, width: 220 })
    : null;

  const desiredStatesByPoint = Object.fromEntries(
    await Promise.all(
      points.map(async (point) => {
        const desiredResponse = await apiFetch(`/points/${point.id}/desired-states`, accessToken);
        const states: DesiredState[] = desiredResponse.ok ? await desiredResponse.json() : [];
        return [point.id, states.filter((state) => state.valid_to === null)] as const;
      }),
    ),
  );

  const rulesByPoint = Object.fromEntries(
    await Promise.all(
      points.map(async (point) => {
        const rulesResponse = await apiFetch(
          `/configs?config_type=alarm_rule&subject_key=${point.id}`,
          accessToken,
        );
        const versions: ConfigVersion[] = rulesResponse.ok ? await rulesResponse.json() : [];
        return [point.id, versions] as const;
      }),
    ),
  );

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
      <Link href="/registre">← {t("common.back")}</Link>

      {passport.functional_location && (
        <h1>
          {passport.functional_location.code} — {passport.functional_location.name}
        </h1>
      )}
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}

      {passport.status && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.status")}</h2>
          <StatusLine status={passport.status} timeZone={timeZone} locale={locale} t={t} />
        </section>
      )}

      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>{t("mobile.passport.unit")}</h2>
        {unit ? (
          <UnitView unit={unit} t={t} nodeId={id} canManage={canManage} locale={locale} />
        ) : (
          <p>{t("mobile.passport.no_unit")}</p>
        )}
      </section>

      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>{t("web.registre.tag_section_title")}</h2>
        {activeTag && tagSvg ? (
          <>
            <div dangerouslySetInnerHTML={{ __html: tagSvg }} />
            <p>
              {t("web.registre.tag_code_label")} : <strong>{activeTag.code}</strong>
            </p>
            {canManage && (
              <form action={revokeTag} style={{ maxWidth: 360 }}>
                <input type="hidden" name="node_id" value={id} />
                <input type="hidden" name="code" value={activeTag.code} />
                <label>
                  {t("web.registre.revoke_reason")}
                  <input name="reason" required style={fieldStyle} />
                </label>
                <button type="submit" style={{ marginTop: 8 }}>
                  {t("web.registre.revoke_tag")}
                </button>
              </form>
            )}
          </>
        ) : (
          <>
            <p>{t("web.registre.no_active_tag")}</p>
            {canManage && (
              <form action={createTagForEquipment}>
                <input type="hidden" name="node_id" value={id} />
                <button type="submit">{t("web.registre.create_tag")}</button>
              </form>
            )}
          </>
        )}
      </section>

      {points.length > 0 && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.latest")}</h2>
          {points.map((point) => (
            <div key={point.id} style={{ marginBottom: 12 }}>
              <p style={{ margin: 0 }}>
                {point.name} —{" "}
                {point.latest
                  ? `${formatNumber(locale, point.latest.value)} ${point.unit} (${formatDateTime(
                      locale,
                      point.latest.measured_at,
                      timeZone,
                    )})`
                  : t("mobile.passport.no_measurement")}
                {point.latest && point.latest.quality_flags.length > 0
                  ? ` — ${t("mobile.passport.flagged")}`
                  : ""}
              </p>
              <DesiredStateBlock
                point={point}
                desiredStates={desiredStatesByPoint[point.id] ?? []}
                nodeId={id}
                canManage={canManage}
                t={t}
                locale={locale}
              />
              <RulesBlock
                point={point}
                versions={rulesByPoint[point.id] ?? []}
                nodeId={id}
                canManage={canManage}
                t={t}
              />
            </div>
          ))}
        </section>
      )}

      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>{t("mobile.passport.signals")}</h2>
        {alarms.map((alarm) => (
          <div key={alarm.id} style={{ marginBottom: 12 }}>
            <p style={{ margin: 0 }}>
              {t("mobile.passport.alarm")} · {t(`severity.${alarm.severity}`)} ·{" "}
              {t(`condition_state.${alarm.condition_state}`)} · {t(`ack_state.${alarm.ack_state}`)} ·{" "}
              {t(`handling_status.${alarm.handling_status}`)}
              <br />
              {alarm.message}
            </p>
            <SignalActions kind="alarm" signal={alarm} nodeId={id} t={t} />
          </div>
        ))}
        {passport.open_findings.map((finding) => (
          <div key={finding.id} style={{ marginBottom: 12 }}>
            <p style={{ margin: 0 }}>
              {t("mobile.passport.finding")} · {t(`severity.${finding.severity}`)} ·{" "}
              {t(`certainty.${finding.certainty}`)} · {t(`condition_state.${finding.condition_state}`)} ·{" "}
              {t(`handling_status.${finding.handling_status}`)}
              <br />
              {finding.title}
            </p>
            <SignalActions
              kind="finding"
              signal={{ ...finding, findingKind: finding.kind }}
              nodeId={id}
              t={t}
            />
          </div>
        ))}
        {alarms.length === 0 && passport.open_findings.length === 0 && (
          <p>{t("mobile.passport.nothing_open")}</p>
        )}
      </section>

      {((passport.open_work_orders && passport.open_work_orders.length > 0) || canManage) && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.work_orders")}</h2>
          {passport.open_work_orders?.map((order) => (
            <p key={order.id}>
              {order.title} ({t(`work_order.status.${order.status}`)})
            </p>
          ))}
          {canManage && (
            <form action={createWorkOrderForEquipment} style={{ maxWidth: 400, marginTop: 12 }}>
              <input type="hidden" name="node_id" value={id} />
              <label>
                {t("web.work_orders.col_title")}
                <input name="title" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.work_orders.col_type")}
                <select name="work_order_type" defaultValue="corrective" style={fieldStyle}>
                  {WORK_ORDER_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`work_order.type.${type}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label style={labelStyle}>
                {t("web.work_orders.col_priority")}
                <select name="priority" defaultValue="medium" style={fieldStyle}>
                  {WORK_ORDER_PRIORITIES.map((priority) => (
                    <option key={priority} value={priority}>
                      {t(`work_order.priority.${priority}`)}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" style={submitStyle}>
                {t("web.work_orders.submit")}
              </button>
            </form>
          )}
        </section>
      )}

      {passport.recent_interventions && passport.recent_interventions.length > 0 && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.interventions")}</h2>
          {passport.recent_interventions.map((item) => (
            <p key={item.id}>
              {formatDate(locale, item.started_at, timeZone)} —{" "}
              {item.action_label ?? item.summary ?? t("mobile.passport.no_summary")}
              {item.symptom_label ? ` (${item.symptom_label})` : ""}
            </p>
          ))}
        </section>
      )}

      <p style={mutedStyle}>
        {timeZone
          ? t("mobile.passport.site_time", { timezone: timeZone })
          : t("mobile.passport.device_time")}
      </p>
    </main>
  );
}

function StatusLine({
  status,
  timeZone,
  locale,
  t,
}: {
  status: EquipmentStatus;
  timeZone: string | null;
  locale: Locale;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const { key, params } = statusMessage(status);
  const rendered = Object.fromEntries(
    Object.entries(params ?? {}).map(([name, value]) => [
      name,
      name === "since" ? formatDateTime(locale, value, timeZone) : t(value),
    ]),
  );
  return <p style={status.current ? strongStyle : undefined}>{t(key, rendered)}</p>;
}

function SignalActions({
  kind,
  signal,
  nodeId,
  t,
}: {
  kind: "alarm" | "finding";
  signal: {
    id: string;
    ack_state: string;
    handling_status: string;
    condition_state: string;
    findingKind?: string;
    certainty?: string;
  };
  nodeId: string;
  t: (key: string) => string;
}) {
  const hidden = (
    <>
      <input type="hidden" name="kind" value={kind} />
      <input type="hidden" name="signal_id" value={signal.id} />
      <input type="hidden" name="node_id" value={nodeId} />
    </>
  );
  const handlingOpen = HANDLING_OPEN.includes(signal.handling_status);
  return (
    <div style={signalActionsStyle}>
      {signal.ack_state === "unacknowledged" && (
        <form action={acknowledgeSignal}>
          {hidden}
          <button type="submit">{t("web.registre.acknowledge")}</button>
        </form>
      )}
      {/* Un signalement ne peut être clos tant que sa condition est active
          (voir app/signals.py, set_handling) : seul le retour à la normale
          (alarme) ou le faux positif restent alors possibles. */}
      {kind === "alarm" && signal.condition_state === "active" && (
        <form action={clearAlarm}>
          {hidden}
          <button type="submit">{t("web.registre.clear_condition")}</button>
        </form>
      )}
      {handlingOpen && signal.condition_state === "cleared" && (
        <form action={setHandling}>
          {hidden}
          <input type="hidden" name="handling_status" value="closed" />
          <button type="submit">{t("web.registre.close_signal")}</button>
        </form>
      )}
      {handlingOpen && (
        <form action={setHandling}>
          {hidden}
          <input type="hidden" name="handling_status" value="false_positive" />
          <button type="submit">{t("web.registre.false_positive")}</button>
        </form>
      )}
      {/* Une prédiction porte sur l'avenir : elle n'est jamais confirmée
          (voir app/findings.py, confirm_finding). */}
      {kind === "finding" && signal.certainty !== "confirmed" && signal.findingKind !== "prediction" && (
        <form action={confirmFinding} style={{ display: "flex", gap: 4 }}>
          {hidden}
          <input name="note" required placeholder={t("web.registre.confirm_note")} />
          <button type="submit">{t("web.registre.confirm_finding")}</button>
        </form>
      )}
    </div>
  );
}

function DesiredStateBlock({
  point,
  desiredStates,
  nodeId,
  canManage,
  t,
  locale,
}: {
  point: { id: string };
  desiredStates: DesiredState[];
  nodeId: string;
  canManage: boolean;
  t: (key: string, params?: Record<string, string>) => string;
  locale: Locale;
}) {
  return (
    <div style={{ marginLeft: 16 }}>
      {desiredStates.map((state) => (
        <p key={state.id} style={mutedStyle}>
          {t("web.registre.desired_state_active", {
            value: formatNumber(locale, state.value),
            since: formatDate(locale, state.valid_from, null),
          })}
          {canManage && (
            <form action={endDesiredState} style={{ display: "inline", marginLeft: 8 }}>
              <input type="hidden" name="desired_state_id" value={state.id} />
              <input type="hidden" name="node_id" value={nodeId} />
              <button type="submit">{t("web.registre.end_desired_state")}</button>
            </form>
          )}
        </p>
      ))}
      {canManage && desiredStates.length === 0 && (
        <details>
          <summary>{t("web.registre.declare_desired_state")}</summary>
          <form action={declareDesiredState} style={{ maxWidth: 360 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <input type="hidden" name="point_id" value={point.id} />
            <label>
              {t("web.registre.desired_state_value")}
              <input name="value" type="number" step="any" required style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.desired_state_reason")}
              <input name="reason" required style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.desired_state_daily_start")}
              <input name="daily_start" type="time" style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.desired_state_daily_end")}
              <input name="daily_end" type="time" style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.desired_state_timezone")}
              <input
                name="timezone"
                placeholder={t("web.registre.site_timezone_placeholder")}
                style={fieldStyle}
              />
            </label>
            <button type="submit" style={submitStyle}>
              {t("web.registre.submit")}
            </button>
          </form>
        </details>
      )}
    </div>
  );
}

function RulesBlock({
  point,
  versions,
  nodeId,
  canManage,
  t,
}: {
  point: { id: string };
  versions: ConfigVersion[];
  nodeId: string;
  canManage: boolean;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  return (
    <div style={{ marginLeft: 16, marginTop: 4 }}>
      <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>{t("web.registre.rules_title")}</p>
      {versions.length === 0 && <p style={mutedStyle}>{t("web.registre.no_rules")}</p>}
      {versions.map((version) => (
        <p key={version.id} style={{ margin: 0 }}>
          {t("web.registre.rule_version", { version: String(version.version) })} —{" "}
          {t(`config_status.${version.status}`)} — {t(`severity.${version.content.severity}`)} —{" "}
          {version.content.title}
          {version.content.kind === "threshold" &&
            ` (${version.content.operator === ">" ? t("web.registre.rule_operator_gt") : t("web.registre.rule_operator_lt")} ${version.content.threshold})`}
          {version.content.kind === "desired_state_divergence" &&
            ` (${t("web.registre.rule_tolerance")}: ${version.content.tolerance})`}
          {canManage && version.status === "draft" && (
            <form action={activateRule} style={{ display: "inline", marginLeft: 8 }}>
              <input type="hidden" name="version_id" value={version.id} />
              <input type="hidden" name="node_id" value={nodeId} />
              <button type="submit">{t("web.registre.activate_rule")}</button>
            </form>
          )}
          {canManage && version.status !== "retired" && (
            <form action={retireRule} style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}>
              <input type="hidden" name="version_id" value={version.id} />
              <input type="hidden" name="node_id" value={nodeId} />
              <input name="reason" required placeholder={t("web.registre.retire_reason")} />
              <button type="submit">{t("web.registre.retire_rule")}</button>
            </form>
          )}
        </p>
      ))}
      {canManage && (
        <>
          <details>
            <summary>{t("web.registre.create_threshold_rule")}</summary>
            <form action={createThresholdRule} style={{ maxWidth: 360 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <input type="hidden" name="point_id" value={point.id} />
              <label>
                {t("web.registre.rule_title")}
                <input name="title" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_severity")}
                <select name="severity" defaultValue="warning" style={fieldStyle}>
                  {["info", "warning", "major", "critical"].map((severity) => (
                    <option key={severity} value={severity}>
                      {t(`severity.${severity}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_operator_gt")} / {t("web.registre.rule_operator_lt")}
                <select name="operator" defaultValue=">" style={fieldStyle}>
                  <option value=">">{t("web.registre.rule_operator_gt")}</option>
                  <option value="<">{t("web.registre.rule_operator_lt")}</option>
                </select>
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_threshold")}
                <input name="threshold" type="number" step="any" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_recommended_action")}
                <input name="recommended_action" style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                <input name="create_work_order" type="checkbox" /> {t("web.registre.rule_create_work_order")}
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_reason")}
                <input name="reason" required style={fieldStyle} />
              </label>
              <button type="submit" style={submitStyle}>
                {t("web.registre.submit")}
              </button>
            </form>
          </details>
          <details>
            <summary>{t("web.registre.create_divergence_rule")}</summary>
            <form action={createDivergenceRule} style={{ maxWidth: 360 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <input type="hidden" name="point_id" value={point.id} />
              <label>
                {t("web.registre.rule_title")}
                <input name="title" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_severity")}
                <select name="severity" defaultValue="warning" style={fieldStyle}>
                  {["info", "warning", "major", "critical"].map((severity) => (
                    <option key={severity} value={severity}>
                      {t(`severity.${severity}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_tolerance")}
                <input name="tolerance" type="number" step="any" min="0" defaultValue="0" style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_recommended_action")}
                <input name="recommended_action" style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                <input name="create_work_order" type="checkbox" /> {t("web.registre.rule_create_work_order")}
              </label>
              <label style={labelStyle}>
                {t("web.registre.rule_reason")}
                <input name="reason" required style={fieldStyle} />
              </label>
              <button type="submit" style={submitStyle}>
                {t("web.registre.submit")}
              </button>
            </form>
          </details>
        </>
      )}
    </div>
  );
}

function UnitView({
  unit,
  t,
  nodeId,
  canManage,
  locale,
}: {
  unit: PassportUnit;
  t: (key: string, params?: Record<string, string>) => string;
  nodeId: string;
  canManage: boolean;
  locale: Locale;
}) {
  const nextStates = LIFECYCLE_TRANSITIONS[unit.lifecycle_state] ?? [];
  const properties = unit.properties ?? [];
  return (
    <>
      <p style={strongStyle}>
        {unit.manufacturer} {unit.reference}
      </p>
      <p>{t("mobile.passport.equipment_type", { type: t(`equipment_type.${unit.equipment_type}`) })}</p>
      {unit.manufacturer_designation && <p style={mutedStyle}>{unit.manufacturer_designation}</p>}
      <p>{t("mobile.passport.serial", { serial: unit.serial_number })}</p>
      {unit.asset_code && <p>{t("mobile.passport.asset_code", { code: unit.asset_code })}</p>}
      {canManage && (
        <form action={setAssetCode} style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <input type="hidden" name="node_id" value={nodeId} />
          <input type="hidden" name="unit_id" value={unit.id} />
          <label>
            {t("web.registre.asset_code_label")}
            <input name="asset_code" defaultValue={unit.asset_code ?? ""} required style={fieldStyle} />
          </label>
          <button type="submit">{t("web.registre.submit")}</button>
        </form>
      )}
      <p>{t("mobile.passport.state", { state: t(`lifecycle.${unit.lifecycle_state}`) })}</p>
      {canManage && nextStates.length > 0 && (
        <form action={changeLifecycleState} style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <input type="hidden" name="node_id" value={nodeId} />
          <input type="hidden" name="physical_unit_id" value={unit.id} />
          <label>
            {t("web.registre.lifecycle_next_state")}
            <select name="to_state" required style={fieldStyle}>
              {nextStates.map((state) => (
                <option key={state} value={state}>
                  {t(`lifecycle.${state}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("web.registre.lifecycle_note")}
            <input name="note" style={fieldStyle} />
          </label>
          <button type="submit">{t("web.registre.change_lifecycle")}</button>
        </form>
      )}

      <p style={{ ...strongStyle, marginTop: 16 }}>{t("web.registre.properties_title")}</p>
      {properties.length === 0 ? (
        <p style={mutedStyle}>{t("web.registre.no_properties")}</p>
      ) : (
        properties.map((property) => (
          <p key={property.id} style={{ margin: 0 }}>
            {t(`property_key.${property.property_key}`)} :{" "}
            {typeof property.value === "number"
              ? formatNumber(locale, property.value)
              : property.value}
            {property.unit ? ` ${property.unit}` : ""}
            {" — "}
            {t(`property_source.${property.source}`)}
          </p>
        ))
      )}
      {canManage && (
        <details>
          <summary>{t("web.registre.add_property")}</summary>
          <form action={setProperty} style={{ maxWidth: 360 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <input type="hidden" name="unit_id" value={unit.id} />
            <label>
              {t("web.registre.property_key")}
              <select name="key" required style={fieldStyle}>
                {PROPERTY_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {t(`property_key.${key}`)}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              {t("web.registre.property_value")}
              <input name="value" required style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.property_unit")}
              <input name="unit" style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.property_source")}
              <select name="source" defaultValue="nameplate" style={fieldStyle}>
                {PROPERTY_SOURCES.map((source) => (
                  <option key={source} value={source}>
                    {t(`property_source.${source}`)}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              {t("web.registre.property_reason")}
              <input name="reason" required style={fieldStyle} />
            </label>
            <button type="submit" style={submitStyle}>
              {t("web.registre.submit")}
            </button>
          </form>
        </details>
      )}
    </>
  );
}
