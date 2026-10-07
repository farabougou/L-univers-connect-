import Link from "next/link";

import { Breadcrumb, type BreadcrumbSegment } from "@/components/Breadcrumb";
import { EnergyBarChart, type EnergyChartPeriod } from "@/components/EnergyBarChart";
import { SignalActions } from "@/components/SignalActions";
import { SiteSwitcher } from "@/components/SiteSwitcher";
import { StatusBadge, equipmentStatusToAssetStatus } from "@/components/StatusBadge";
import { Timeline, type TimelineEntry } from "@/components/Timeline";
import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  badgeStyle,
  cardStyle,
  colors,
  fieldStyle,
  labelStyle,
  pageContainerStyle,
  sectionTitleStyle,
  submitStyle,
} from "@/lib/formStyles";
import { SEVERITY_COLOR, type Severity } from "@/lib/portfolio";
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import {
  type DesiredState,
  type EquipmentStatus,
  type Passport,
  type PassportCommand,
  type PassportUnit,
  statusMessage,
} from "@/lib/passport";
import {
  COMMAND_ROLES,
  type Me,
  canManage as computeCanManage,
  canSendCommand as computeCanSendCommand,
} from "@/lib/roles";
import { renderTagQr } from "@/lib/tagQr";
import {
  type Locale,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatNumber,
} from "@/i18n/translator";

import {
  acceptBacnetProposal,
  acknowledgeSignal,
  activateRule,
  cancelScheduledTestCommand,
  changeLifecycleState,
  clearAlarm,
  computeEnergyResult,
  confirmFinding,
  createAutomationRule,
  createBacnetDeviceMapping,
  createCommandPolicy,
  createCorrelationRule,
  createDeviceMapping,
  createDivergenceRule,
  createEnergyBaseline,
  createPointControlMode,
  createSimulatedRelayMapping,
  createTagForEquipment,
  createThresholdRule,
  createWorkOrderForEquipment,
  declareDesiredState,
  declareMaintenanceProvider,
  endDesiredState,
  endMaintenanceProvider,
  rejectBacnetProposal,
  restoreRule,
  retireRule,
  revokeTag,
  scanBacnetDevice,
  scheduleTestCommand,
  sendTestCommand,
  setAssetCode,
  setHandling,
  setProperty,
} from "./actions";

type ScheduledCommand = {
  id: string;
  requested_value: number;
  scheduled_for: string;
  status: "pending" | "dispatched" | "cancelled" | "failed";
  failure_reason: string | null;
};

type PointControlModeVersion = {
  id: string;
  version: number;
  status: string;
  content: { mode: "manual" | "automatic" };
};

type CommandPointPolicyVersion = {
  id: string;
  version: number;
  status: string;
  content: { allowed_roles: string[] | null; allowed_values: number[] | null };
};

type AutomationRuleContent = {
  title: string;
  trigger_point_id: string;
  operator: ">" | "<";
  threshold: number;
  target_point_id: string;
  requested_value: number;
};
type AutomationRuleVersion = {
  id: string;
  version: number;
  status: string;
  content: AutomationRuleContent;
};

type ImpactedNode = {
  node_id: string;
  node_type: string;
  open_finding_count: number;
  code: string | null;
  name: string | null;
};
type ImpactReport = {
  node_id: string;
  open_finding_count: number;
  impacted: ImpactedNode[];
};
type RuleContent = {
  kind: "threshold" | "desired_state_divergence" | "simultaneous_heating_cooling";
  severity: string;
  title: string;
  operator?: string;
  threshold?: number;
  tolerance?: number;
  heating_point_id?: string;
  cooling_point_id?: string;
  heating_threshold?: number;
  cooling_threshold?: number;
};
type ConfigVersion = {
  id: string;
  version: number;
  status: string;
  content: RuleContent;
  parent_version_id: string | null;
};
type ConfigDiff = {
  from_version: number;
  to_version: number;
  added: Record<string, unknown>;
  removed: Record<string, unknown>;
  changed: Record<string, { from: unknown; to: unknown }>;
};
type RuleSimulation = {
  sample_size: number;
  breach_count: number;
  breaches: { measured_at: string; value: number | boolean }[];
};

type DeviceMappingContent = {
  device_type: string;
  host: string;
  port: number;
  points: { point_id: string; register_name: string }[];
};
type DeviceMappingVersion = {
  id: string;
  version: number;
  status: string;
  content: DeviceMappingContent;
  parent_version_id: string | null;
};
// Connexion BACnet (ADR 015) : pas de catalogue de registres, le protocole
// normalise déjà l'adressage d'un point (type d'objet, instance, propriété).
type BacnetMappingContent = {
  address: string;
  points: { point_id: string; object_type: string; object_instance: number }[];
};
type BacnetMappingVersion = {
  id: string;
  version: number;
  status: string;
  content: BacnetMappingContent;
  parent_version_id: string | null;
};
// Un résultat de performance normalisée (app/energy/normalization.py) : voir
// aussi CLAUDE.md, section M5 — jamais présenté comme un calcul OPERAT.
type EnergyEstimatedCost = {
  amount: number;
  currency: string;
  price_per_kwh: number;
  basis: "normalized" | "raw";
};
type EnergyNormalizedResult = {
  id: string;
  period_start: string;
  period_end: string;
  raw_consumption: number;
  raw_consumption_unit: string;
  normalization_status: "ok" | "no_weather_data" | "zero_degree_days";
  normalized_consumption: number | null;
  computed_at: string;
  // Null tant qu'aucun tarif n'est actif pour le site (app.economics, V2
  // 02/10/2026) — jamais un coût à zéro ou par défaut.
  estimated_cost: EnergyEstimatedCost | null;
};
type EnergyComparison = {
  comparable: boolean;
  percent_deviation: number | null;
  reduced: boolean | null;
};

type Provider = { id: string; name: string };
type Relation = {
  id: string | null;
  predicate: string;
  object_id: string;
  object_type: string;
  valid_from: string | null;
};
// Référence énergétique (app/energy/baseline.py) : une configuration
// versionnée de plus, figée une fois activée.
type EnergyBaselineContent = {
  point_id: string;
  reference_period: { start: string; end: string };
  degree_day_base_temperature_celsius: number;
  degree_day_kind: "heating" | "cooling";
};
type EnergyBaselineVersion = {
  id: string;
  version: number;
  status: string;
  content: EnergyBaselineContent;
  parent_version_id: string | null;
};

// Un lot de découverte BACnet (app/bacnet_discovery.py) : un scan produit
// des propositions, jamais des points directement créés.
type BacnetDiscoveryBatch = {
  id: string;
  equipment_id: string;
  address: string;
  timeout_seconds: number;
  device_instance: number | null;
  status: "processing" | "ready" | "failed";
  error_code: string | null;
  object_count: number | null;
  proposal_count: number | null;
  duplicate_count: number | null;
  scanned_by: string;
  scanned_at: string;
};
type BacnetDiscoveryProposal = {
  id: string;
  batch_id: string;
  object_type: string;
  object_instance: number;
  object_name: string | null;
  description: string | null;
  bacnet_units: string | null;
  present_value_preview: string | null;
  value_type: "number" | "boolean" | "multistate";
  states: Record<string, string> | null;
  proposed_point_class: string | null;
  proposed_unit: string | null;
  confidence: number | null;
  reason_code: string;
  reason_message: string;
  status: "proposed" | "accepted" | "rejected" | "duplicate";
  created_point_id: string | null;
  decided_by: string | null;
  decided_at: string | null;
  rejection_reason: string | null;
  created_at: string;
};

// Même catalogue que app/connectors/sdm120.py (SDM120_POINTS) : un seul
// modèle d'appareil pour l'instant, pas de saisie libre du registre.
const SDM120_REGISTERS = ["voltage", "current", "active_power", "frequency", "total_active_energy"];

// Mêmes types d'objet que app/connectors/bacnet.py (_DISCOVERABLE_OBJECT_TYPES) :
// vocabulaire du protocole BACnet lui-même, jamais traduit (comme le nom
// d'un objet ou son unité BACnet, déjà montrés tels quels dans la
// découverte) — ce n'est pas un terme du glossaire produit.
const BACNET_DISCOVERABLE_OBJECT_TYPES = [
  "analog-input",
  "analog-output",
  "analog-value",
  "binary-input",
  "binary-output",
  "binary-value",
  "multi-state-input",
  "multi-state-output",
  "multi-state-value",
];

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

const WORK_ORDER_TYPES = ["corrective", "preventive", "predictive", "inspection"];
const WORK_ORDER_PRIORITIES = ["low", "medium", "high", "urgent"];

const mutedStyle = { color: colors.textMuted };
const strongStyle = { fontWeight: 600 as const };
const signalActionsStyle = { display: "flex", gap: 8, marginTop: 4 };

export default async function EquipmentPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{
    error?: string;
    diff?: string;
    against?: string;
    simulate?: string;
    timeline_before?: string;
    bacnet_batch?: string;
  }>;
}) {
  const { id } = await params;
  const {
    error: errorCode,
    diff: diffVersionId,
    against,
    simulate: simulateVersionId,
    timeline_before: timelineBefore,
    bacnet_batch: bacnetBatchId,
  } = await searchParams;
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const locale = await getLocale();
  const { t } = translator;
  const error = errorCode
    ? (errorMessage(translator.locale, errorCode) ?? t("web.registre.creation_failed"))
    : null;

  let configDiff: ConfigDiff | null = null;
  if (diffVersionId && against) {
    const diffResponse = await apiFetch(
      `/configs/${diffVersionId}/diff?against=${against}`,
      accessToken,
    );
    configDiff = diffResponse.ok ? await diffResponse.json() : null;
  }

  let ruleSimulation: RuleSimulation | null = null;
  if (simulateVersionId) {
    const simulationResponse = await apiFetch(
      `/configs/${simulateVersionId}/simulate`,
      accessToken,
    );
    ruleSimulation = simulationResponse.ok ? await simulationResponse.json() : null;
  }

  const timelineQuery = timelineBefore
    ? `?before=${encodeURIComponent(timelineBefore)}&limit=20`
    : "?limit=20";
  const [
    response,
    meResponse,
    providersResponse,
    relationsResponse,
    timelineResponse,
    sitesResponse,
    impactResponse,
  ] = await Promise.all([
    apiFetch(`/graph/nodes/${id}/passport`, accessToken),
    apiFetch("/me", accessToken),
    apiFetch("/providers", accessToken),
    apiFetch(`/graph/nodes/${id}/relations`, accessToken),
    apiFetch(`/graph/nodes/${id}/timeline${timelineQuery}`, accessToken),
    apiFetch("/sites", accessToken),
    apiFetch(`/graph/nodes/${id}/impact`, accessToken),
  ]);
  const sites: { id: string; name: string }[] = sitesResponse.ok ? await sitesResponse.json() : [];
  const impactReport: ImpactReport | null = impactResponse.ok
    ? await impactResponse.json()
    : null;
  const providers: Provider[] = providersResponse.ok ? await providersResponse.json() : [];
  const relations: Relation[] = relationsResponse.ok ? await relationsResponse.json() : [];
  const maintenanceProviders = relations.filter((relation) => relation.predicate === "maintainedBy");
  const providerName = (providerId: string) =>
    providers.find((provider) => provider.id === providerId)?.name ?? providerId;
  const timeline: TimelineEntry[] = timelineResponse.ok ? await timelineResponse.json() : [];
  const me: Me = meResponse.ok ? await meResponse.json() : { roles: [] };
  const canManage = computeCanManage(me);
  const canSendCommand = computeCanSendCommand(me);
  if (!response.ok) {
    return (
      <main style={pageContainerStyle}>
        <Link href="/registre" style={{ color: colors.accent }}>
          ← {t("common.back")}
        </Link>
        <p style={{ color: colors.textMuted }}>{t("web.registre.equipment_not_found")}</p>
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
    ? await renderTagQr(activeTag.payload)
    : null;

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

  // Règle FDD à deux points (app/rules.py, CorrelationRule) : portée sur
  // l'équipement entier, pas sur un point précis, donc récupérée à part de
  // rulesByPoint ci-dessus.
  const correlationRuleResponse = await apiFetch(
    `/configs?config_type=alarm_rule&subject_key=${id}`,
    accessToken,
  );
  const correlationRuleVersions: ConfigVersion[] = correlationRuleResponse.ok
    ? await correlationRuleResponse.json()
    : [];
  const numericPoints = points.filter((point) => point.value_type === "number");

  const deviceMappingResponse = await apiFetch(
    `/configs?config_type=modbus_device_mapping&subject_key=${id}`,
    accessToken,
  );
  const deviceMappingVersions: DeviceMappingVersion[] = deviceMappingResponse.ok
    ? await deviceMappingResponse.json()
    : [];

  const bacnetMappingResponse = await apiFetch(
    `/configs?config_type=bacnet_device_mapping&subject_key=${id}`,
    accessToken,
  );
  const bacnetMappingVersions: BacnetMappingVersion[] = bacnetMappingResponse.ok
    ? await bacnetMappingResponse.json()
    : [];

  // Le relais simulé (test de commande) est une version active dont le
  // device_type le désigne explicitement — jamais un vrai appareil (voir
  // CLAUDE.md, exception à la règle non négociable 1).
  const activeRelayMapping = deviceMappingVersions.find(
    (version) => version.status === "active" && version.content.device_type === "simulated_relay",
  );
  const relayPointId = activeRelayMapping?.content.points[0]?.point_id ?? null;
  const relayPoint = relayPointId ? points.find((point) => point.id === relayPointId) : null;
  const lastCommand: PassportCommand | null = relayPoint?.commands[0] ?? null;

  // Commandes planifiées (V2, priorité « planification ») : même point que
  // la commande immédiate ci-dessus, jamais un deuxième mécanisme de
  // commandabilité.
  let scheduledCommands: ScheduledCommand[] = [];
  if (relayPointId) {
    const scheduledResponse = await apiFetch(
      `/scheduled-commands?point_id=${relayPointId}&limit=5`,
      accessToken,
    );
    scheduledCommands = scheduledResponse.ok ? await scheduledResponse.json() : [];
  }

  // Mode du point (V2, priorité « modes/consignes ») : manuel par défaut,
  // verrou qui conditionne l'automatisation ci-dessous (app.point_control_mode).
  let controlModeVersions: PointControlModeVersion[] = [];
  if (relayPointId) {
    const modeResponse = await apiFetch(
      `/configs?config_type=point_control_mode&subject_key=${relayPointId}`,
      accessToken,
    );
    controlModeVersions = modeResponse.ok ? await modeResponse.json() : [];
  }
  const activeControlMode =
    controlModeVersions.find((version) => version.status === "active")?.content.mode ?? "manual";

  // Règles d'automatisation (V2, dernière priorité) : portées par le point
  // commandé (subject_key = relayPointId), jamais par le point déclencheur
  // (qui peut varier d'une règle à l'autre) — voir app/automation_rules.py.
  let automationRuleVersions: AutomationRuleVersion[] = [];
  if (relayPointId) {
    const automationResponse = await apiFetch(
      `/configs?config_type=automation_rule&subject_key=${relayPointId}`,
      accessToken,
    );
    automationRuleVersions = automationResponse.ok ? await automationResponse.json() : [];
  }

  // Policy de commande (V2, priorité « autorisation/policies »,
  // app.command_policies) : restreint, pour CE point précis, quels rôles et
  // quelles valeurs sont acceptés — au-delà des rôles globaux déjà vérifiés
  // par /commands. Le moteur existait déjà côté API depuis le 02/10/2026
  // mais n'avait jamais eu d'écran : sans lui, une policy ne pouvait être
  // posée que par un appel direct à l'API (trouvé lors de l'audit de
  // fermeture V2 du 07/10/2026).
  let commandPolicyVersions: CommandPointPolicyVersion[] = [];
  if (relayPointId) {
    const policyResponse = await apiFetch(
      `/configs?config_type=command_point_policy&subject_key=${relayPointId}`,
      accessToken,
    );
    commandPolicyVersions = policyResponse.ok ? await policyResponse.json() : [];
  }

  // Découverte BACnet (BACnet V1, lecture seule) : mêmes principes que la
  // connexion Modbus ci-dessus, sujet = l'équipement (voir
  // app/bacnet_discovery.py). Un équipement introuvable côté API (nœud qui
  // n'est pas un functional_location) laisse simplement la liste vide.
  const bacnetBatchesResponse = await apiFetch(
    `/bacnet-discovery/batches?equipment_id=${id}`,
    accessToken,
  );
  const bacnetBatches: BacnetDiscoveryBatch[] = bacnetBatchesResponse.ok
    ? await bacnetBatchesResponse.json()
    : [];
  let bacnetProposals: BacnetDiscoveryProposal[] = [];
  if (bacnetBatchId) {
    const bacnetProposalsResponse = await apiFetch(
      `/bacnet-discovery/batches/${bacnetBatchId}/proposals`,
      accessToken,
    );
    bacnetProposals = bacnetProposalsResponse.ok ? await bacnetProposalsResponse.json() : [];
  }

  // La performance énergétique porte sur un équipement (functional_location),
  // jamais sur un exemplaire ou un espace (voir app/energy/normalization.py).
  let energyResults: EnergyNormalizedResult[] = [];
  let energyComparison: EnergyComparison | null = null;
  let energyBaselineVersions: EnergyBaselineVersion[] = [];
  if (passport.node_type === "functional_location") {
    const [energyResponse, energyBaselineResponse] = await Promise.all([
      apiFetch(`/energy/normalized-results?functional_location_id=${id}`, accessToken),
      apiFetch(`/configs?config_type=energy_baseline&subject_key=${id}`, accessToken),
    ]);
    energyResults = energyResponse.ok ? await energyResponse.json() : [];
    energyBaselineVersions = energyBaselineResponse.ok ? await energyBaselineResponse.json() : [];
    if (energyResults.length >= 2) {
      const comparisonResponse = await apiFetch(
        `/energy/comparison?reference_result_id=${energyResults[1].id}&analyzed_result_id=${energyResults[0].id}`,
        accessToken,
      );
      energyComparison = comparisonResponse.ok ? await comparisonResponse.json() : null;
    }
  }
  const activeEnergyBaseline = energyBaselineVersions.find((version) => version.status === "active");

  return (
    <main style={pageContainerStyle}>
      <Link href="/registre" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>

      {passport.functional_location && (
        <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
          {passport.functional_location.code} — {passport.functional_location.name}
        </h1>
      )}
      {error && <p style={{ color: colors.danger }}>{error}</p>}

      {configDiff && (
        <section
          style={{ border: `1px solid ${colors.accent}`, borderRadius: 8, padding: 16, margin: "16px 0" }}
        >
          <h2 style={sectionTitleStyle}>
            {t("web.registre.rule_diff_title", {
              from: String(configDiff.from_version),
              to: String(configDiff.to_version),
            })}
          </h2>
          {Object.entries(configDiff.changed).map(([key, value]) => (
            <p key={key} style={{ margin: 0 }}>
              {key} : {String(value.from)} → {String(value.to)}
            </p>
          ))}
          {Object.entries(configDiff.added).map(([key, value]) => (
            <p key={key} style={{ margin: 0 }}>
              + {key} : {String(value)}
            </p>
          ))}
          {Object.entries(configDiff.removed).map(([key, value]) => (
            <p key={key} style={{ margin: 0 }}>
              − {key} : {String(value)}
            </p>
          ))}
          {Object.keys(configDiff.changed).length === 0 &&
            Object.keys(configDiff.added).length === 0 &&
            Object.keys(configDiff.removed).length === 0 && <p>{t("web.registre.rule_diff_none")}</p>}
          <Link href={`/registre/${id}`}>{t("web.registre.tag_close")}</Link>
        </section>
      )}

      {ruleSimulation && (
        <section
          style={{ border: `1px solid ${colors.accent}`, borderRadius: 8, padding: 16, margin: "16px 0" }}
        >
          <h2 style={sectionTitleStyle}>{t("web.registre.rule_simulation_title")}</h2>
          <p style={{ margin: 0 }}>
            {t("web.registre.rule_simulation_summary", {
              breach_count: String(ruleSimulation.breach_count),
              sample_size: String(ruleSimulation.sample_size),
            })}
          </p>
          {ruleSimulation.breaches.map((breach, index) => (
            <p key={index} style={{ margin: 0 }}>
              {t("web.registre.rule_simulation_breach_line", {
                measured_at: formatDateTime(locale, breach.measured_at, null),
                value: String(breach.value),
              })}
            </p>
          ))}
          <Link href={`/registre/${id}`}>{t("web.registre.tag_close")}</Link>
        </section>
      )}

      <IdentityHeader
        passport={passport}
        unit={unit}
        timeZone={timeZone}
        locale={locale}
        sites={sites}
        t={t}
      />

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>{t("mobile.passport.unit")}</h2>
        {unit ? (
          <UnitView unit={unit} t={t} nodeId={id} canManage={canManage} locale={locale} />
        ) : (
          <p>{t("mobile.passport.no_unit")}</p>
        )}
      </section>

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>{t("web.registre.maintenance_provider_title")}</h2>
        {maintenanceProviders.length === 0 ? (
          <p style={mutedStyle}>{t("web.registre.no_maintenance_provider")}</p>
        ) : (
          maintenanceProviders.map((relation) => (
            <p key={relation.id} style={{ margin: 0 }}>
              {providerName(relation.object_id)}
              {relation.valid_from &&
                ` — ${t("web.registre.maintenance_provider_since", { date: formatDate(locale, relation.valid_from, timeZone) })}`}
              {canManage && relation.id && (
                <form
                  action={endMaintenanceProvider}
                  style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}
                >
                  <input type="hidden" name="node_id" value={id} />
                  <input type="hidden" name="relation_id" value={relation.id} />
                  <input name="reason" required placeholder={t("web.registre.end_maintenance_provider_reason")} />
                  <button type="submit">{t("web.registre.end_maintenance_provider")}</button>
                </form>
              )}
            </p>
          ))
        )}
        {canManage && (
          <details style={{ marginTop: 8 }}>
            <summary>{t("web.registre.declare_maintenance_provider")}</summary>
            {providers.length === 0 ? (
              <p style={mutedStyle}>{t("web.registre.no_providers_yet")}</p>
            ) : (
              <form action={declareMaintenanceProvider} style={{ maxWidth: 360 }}>
                <input type="hidden" name="node_id" value={id} />
                <label>
                  {t("web.registre.maintenance_provider_select")}
                  <select name="provider_id" required style={fieldStyle}>
                    {providers.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="submit" style={submitStyle}>
                  {t("web.registre.submit")}
                </button>
              </form>
            )}
          </details>
        )}
      </section>

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>
          {t("timeline.title")}
          {timelineBefore && (
            <>
              {" — "}
              <Link href={`/registre/${id}`} style={{ fontSize: 14 }}>
                {t("common.back")}
              </Link>
            </>
          )}
        </h2>
        <Timeline
          entries={timeline}
          timeZone={timeZone}
          locale={locale}
          loadOlderHref={
            timeline.length === 20
              ? `/registre/${id}?timeline_before=${encodeURIComponent(
                  timeline[timeline.length - 1].at,
                )}`
              : null
          }
          t={t}
        />
      </section>

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>{t("web.registre.impact_section_title")}</h2>
        <ImpactBlock report={impactReport} t={t} />
      </section>

      <section style={{ ...cardStyle, marginTop: 16 }}>
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
        <section style={{ ...cardStyle, marginTop: 16 }}>
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
                desiredStates={point.desired_states}
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

      {numericPoints.length >= 2 && (
        <section style={{ ...cardStyle, marginTop: 16 }}>
          <h2 style={sectionTitleStyle}>{t("web.registre.correlation_rule_section_title")}</h2>
          <CorrelationRuleBlock
            nodeId={id}
            numericPoints={numericPoints}
            versions={correlationRuleVersions}
            canManage={canManage}
            t={t}
          />
        </section>
      )}

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>{t("web.registre.modbus_section_title")}</h2>
        <DeviceMappingBlock
          nodeId={id}
          points={points}
          versions={deviceMappingVersions}
          canManage={canManage}
          t={t}
        />
      </section>

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>{t("web.registre.bacnet_section_title")}</h2>
        <BacnetDiscoveryBlock
          nodeId={id}
          batches={bacnetBatches}
          selectedBatchId={bacnetBatchId ?? null}
          proposals={bacnetProposals}
          canManage={canManage}
          locale={locale}
          timeZone={timeZone}
          t={t}
        />
      </section>

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>{t("web.registre.bacnet_mapping_section_title")}</h2>
        <BacnetMappingBlock
          nodeId={id}
          points={points}
          versions={bacnetMappingVersions}
          canManage={canManage}
          t={t}
        />
      </section>

      {(activeRelayMapping || canManage) && (
        <section style={{ ...cardStyle, marginTop: 16 }}>
          <h2 style={sectionTitleStyle}>{t("web.registre.command_section_title")}</h2>
          <CommandBlock
            nodeId={id}
            points={points}
            relayPointId={relayPointId}
            lastCommand={lastCommand}
            scheduledCommands={scheduledCommands}
            activeControlMode={activeControlMode}
            controlModeVersions={controlModeVersions}
            automationRuleVersions={automationRuleVersions}
            commandPolicyVersions={commandPolicyVersions}
            canSendCommand={canSendCommand}
            canManage={canManage}
            locale={locale}
            timeZone={timeZone}
            t={t}
          />
        </section>
      )}

      {passport.node_type === "functional_location" && (
        <section style={{ ...cardStyle, marginTop: 16 }}>
          <h2 style={sectionTitleStyle}>{t("web.registre.energy_baseline_title")}</h2>
          <EnergyBaselineBlock
            nodeId={id}
            points={points}
            versions={energyBaselineVersions}
            canManage={canManage}
            locale={locale}
            t={t}
          />
        </section>
      )}

      {passport.node_type === "functional_location" && (
        <section style={{ ...cardStyle, marginTop: 16 }}>
          <h2 style={sectionTitleStyle}>{t("web.registre.energy_section_title")}</h2>
          <EnergyBlock
            results={energyResults}
            comparison={energyComparison}
            activeBaseline={activeEnergyBaseline ?? null}
            nodeId={id}
            canManage={canManage}
            locale={locale}
            timeZone={timeZone}
            t={t}
          />
        </section>
      )}

      <section style={{ ...cardStyle, marginTop: 16 }}>
        <h2 style={sectionTitleStyle}>{t("mobile.passport.signals")}</h2>
        {alarms.map((alarm) => (
          <div key={alarm.id} style={{ marginBottom: 12 }}>
            <p style={{ margin: 0 }}>
              {t("mobile.passport.alarm")}{" "}
              <span style={badgeStyle(SEVERITY_COLOR[alarm.severity as Severity])}>
                {t(`severity.${alarm.severity}`)}
              </span>{" "}
              · {t(`condition_state.${alarm.condition_state}`)} · {t(`ack_state.${alarm.ack_state}`)} ·{" "}
              {t(`handling_status.${alarm.handling_status}`)}
              <br />
              {alarm.message}
            </p>
            <SignalActions
              kind="alarm"
              signal={alarm}
              nodeId={id}
              actions={{ acknowledgeSignal, clearAlarm, setHandling, confirmFinding }}
              t={t}
            />
          </div>
        ))}
        {passport.open_findings.map((finding) => (
          <div key={finding.id} style={{ marginBottom: 12 }}>
            <p style={{ margin: 0 }}>
              {t("mobile.passport.finding")}{" "}
              <span style={badgeStyle(SEVERITY_COLOR[finding.severity as Severity])}>
                {t(`severity.${finding.severity}`)}
              </span>{" "}
              · {t(`certainty.${finding.certainty}`)} · {t(`condition_state.${finding.condition_state}`)} ·{" "}
              {t(`handling_status.${finding.handling_status}`)}
              <br />
              {finding.title}
            </p>
            <SignalActions
              kind="finding"
              signal={{ ...finding, findingKind: finding.kind }}
              nodeId={id}
              actions={{ acknowledgeSignal, clearAlarm, setHandling, confirmFinding }}
              t={t}
            />
          </div>
        ))}
        {alarms.length === 0 && passport.open_findings.length === 0 && (
          <p>{t("mobile.passport.nothing_open")}</p>
        )}
      </section>

      {((passport.open_work_orders && passport.open_work_orders.length > 0) || canManage) && (
        <section style={{ ...cardStyle, marginTop: 16 }}>
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
        <section style={{ ...cardStyle, marginTop: 16 }}>
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

/**
 * En-tête consolidé de la fiche équipement (directive UI/dashboard, section
 * 21) : « comprendre l'état d'un équipement en quelques secondes » — statut
 * universel, identité et localisation réunis en un seul bloc, avant les
 * sections techniques détaillées plus bas (inchangées). Remplace l'ancienne
 * section « statut » isolée, sans dupliquer `StatusLine` ni `UnitView`.
 */
function IdentityHeader({
  passport,
  unit,
  timeZone,
  locale,
  sites,
  t,
}: {
  passport: Passport;
  unit: PassportUnit | null;
  timeZone: string | null;
  locale: Locale;
  sites: { id: string; name: string }[];
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const assetStatus = passport.status ? equipmentStatusToAssetStatus(passport.status) : "unknown";
  const spacePath = passport.space_path ?? [];
  const segments: BreadcrumbSegment[] = [
    { label: t("common.home"), href: "/" },
    ...(passport.site ? [{ label: passport.site.name, href: `/registre#site-${passport.site.id}` }] : []),
    ...spacePath.map((space) => ({ label: space.name, href: null })),
    ...(passport.functional_location
      ? [{ label: passport.functional_location.code, href: null }]
      : []),
  ];
  return (
    <section style={{ ...cardStyle, marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
        <Breadcrumb segments={segments} />
        <SiteSwitcher
          sites={sites}
          currentSiteId={passport.site?.id ?? null}
          label={t("breadcrumb.switch_site")}
        />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
        <StatusBadge status={assetStatus} label={t(`asset_status.${assetStatus}`)} />
        {passport.status && (
          <StatusLine status={passport.status} timeZone={timeZone} locale={locale} t={t} />
        )}
      </div>
      {unit && (
        <p style={{ color: colors.textMuted, marginTop: 8 }}>
          {unit.manufacturer} {unit.reference}
          {" — "}
          {t(`equipment_type.${unit.equipment_type}`)}
          {" · "}
          {t("mobile.passport.serial", { serial: unit.serial_number })}
        </p>
      )}
    </section>
  );
}

function ImpactBlock({
  report,
  t,
}: {
  report: ImpactReport | null;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  if (report === null) {
    return <p style={mutedStyle}>{t("web.registre.impact_unavailable")}</p>;
  }
  return (
    <>
      <p style={mutedStyle}>{t("web.registre.impact_intro")}</p>
      {report.impacted.length === 0 ? (
        <p>{t("web.registre.impact_no_dependents")}</p>
      ) : (
        <table style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", paddingRight: 16 }}>
                {t("web.registre.impact_col_equipment")}
              </th>
              <th style={{ textAlign: "left" }}>
                {t("web.registre.impact_col_open_findings")}
              </th>
            </tr>
          </thead>
          <tbody>
            {report.impacted.map((node) => (
              <tr key={node.node_id}>
                <td style={{ paddingRight: 16 }}>
                  {node.name ? (
                    <Link href={`/registre/${node.node_id}`} style={{ color: colors.accent }}>
                      {node.code} — {node.name}
                    </Link>
                  ) : (
                    t(`search_result_kind.${node.node_type}`)
                  )}
                </td>
                <td>{node.open_finding_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
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
          {" — "}
          <Link href={`/registre/${nodeId}?simulate=${version.id}`}>
            {t("web.registre.rule_simulate_link")}
          </Link>
          {version.parent_version_id && (
            <>
              {" — "}
              <Link href={`/registre/${nodeId}?diff=${version.id}&against=${version.parent_version_id}`}>
                {t("web.registre.rule_diff_link")}
              </Link>
            </>
          )}
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
          {canManage && version.status === "retired" && (
            <form action={restoreRule} style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}>
              <input type="hidden" name="version_id" value={version.id} />
              <input type="hidden" name="node_id" value={nodeId} />
              <input name="reason" required placeholder={t("web.registre.restore_reason")} />
              <button type="submit">{t("web.registre.restore_rule")}</button>
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

// Règle FDD à deux points (app/rules.py, CorrelationRule) : une seule règle
// de ce type par équipement (subject_key = l'équipement), jamais une liste
// par point comme RulesBlock ci-dessus.
function CorrelationRuleBlock({
  nodeId,
  numericPoints,
  versions,
  canManage,
  t,
}: {
  nodeId: string;
  numericPoints: { id: string; code: string; name: string }[];
  versions: ConfigVersion[];
  canManage: boolean;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const pointLabel = (pointId: string) =>
    numericPoints.find((point) => point.id === pointId)?.code ?? pointId;
  return (
    <div>
      {versions.length === 0 && <p style={mutedStyle}>{t("web.registre.no_rules")}</p>}
      {versions.map((version) => (
        <p key={version.id} style={{ margin: 0 }}>
          {t("web.registre.rule_version", { version: String(version.version) })} —{" "}
          {t(`config_status.${version.status}`)} — {t(`severity.${version.content.severity}`)} —{" "}
          {version.content.title}
          {version.content.heating_point_id && version.content.cooling_point_id && (
            ` (${t("web.registre.rule_heating_point")}: ${pointLabel(version.content.heating_point_id)} — ${t("web.registre.rule_cooling_point")}: ${pointLabel(version.content.cooling_point_id)})`
          )}
          {" — "}
          <Link href={`/registre/${nodeId}?simulate=${version.id}`}>
            {t("web.registre.rule_simulate_link")}
          </Link>
          {version.parent_version_id && (
            <>
              {" — "}
              <Link href={`/registre/${nodeId}?diff=${version.id}&against=${version.parent_version_id}`}>
                {t("web.registre.rule_diff_link")}
              </Link>
            </>
          )}
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
          {canManage && version.status === "retired" && (
            <form action={restoreRule} style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}>
              <input type="hidden" name="version_id" value={version.id} />
              <input type="hidden" name="node_id" value={nodeId} />
              <input name="reason" required placeholder={t("web.registre.restore_reason")} />
              <button type="submit">{t("web.registre.restore_rule")}</button>
            </form>
          )}
        </p>
      ))}
      {canManage && (
        <details>
          <summary>{t("web.registre.create_correlation_rule")}</summary>
          <form action={createCorrelationRule} style={{ maxWidth: 360 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <label style={labelStyle}>
              {t("web.registre.rule_heating_point")}
              <select name="heating_point_id" required style={fieldStyle}>
                {numericPoints.map((point) => (
                  <option key={point.id} value={point.id}>
                    {point.code} — {point.name}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              {t("web.registre.rule_heating_threshold")}
              <input
                name="heating_threshold"
                type="number"
                step="any"
                min="0"
                defaultValue="0"
                style={fieldStyle}
              />
            </label>
            <label style={labelStyle}>
              {t("web.registre.rule_cooling_point")}
              <select name="cooling_point_id" required style={fieldStyle}>
                {numericPoints.map((point) => (
                  <option key={point.id} value={point.id}>
                    {point.code} — {point.name}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              {t("web.registre.rule_cooling_threshold")}
              <input
                name="cooling_threshold"
                type="number"
                step="any"
                min="0"
                defaultValue="0"
                style={fieldStyle}
              />
            </label>
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
      )}
    </div>
  );
}

function DeviceMappingBlock({
  nodeId,
  points,
  versions,
  canManage,
  t,
}: {
  nodeId: string;
  points: { id: string; name: string }[];
  versions: DeviceMappingVersion[];
  canManage: boolean;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const pointName = (pointId: string) => points.find((p) => p.id === pointId)?.name ?? pointId;
  return (
    <>
      {versions.length === 0 && <p style={mutedStyle}>{t("web.registre.modbus_no_mapping")}</p>}
      {versions.map((version) => (
        <div key={version.id} style={{ marginBottom: 12 }}>
          <p style={{ margin: 0 }}>
            {t("web.registre.rule_version", { version: String(version.version) })} —{" "}
            {t(`config_status.${version.status}`)} —{" "}
            {t("web.registre.modbus_summary", {
              device: t(`modbus_device_type.${version.content.device_type}`),
              host: version.content.host,
              port: String(version.content.port),
            })}
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
            {canManage && version.status === "retired" && (
              <form action={restoreRule} style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}>
                <input type="hidden" name="version_id" value={version.id} />
                <input type="hidden" name="node_id" value={nodeId} />
                <input name="reason" required placeholder={t("web.registre.restore_reason")} />
                <button type="submit">{t("web.registre.restore_rule")}</button>
              </form>
            )}
          </p>
          <p style={{ ...mutedStyle, margin: 0, marginLeft: 16 }}>
            {t("web.registre.modbus_points_title")} :{" "}
            {version.content.points
              .map(
                (entry) => `${pointName(entry.point_id)} (${t(`modbus_register.${entry.register_name}`)})`,
              )
              .join(", ")}
          </p>
        </div>
      ))}
      {canManage &&
        (points.length === 0 ? (
          <p style={mutedStyle}>{t("web.registre.modbus_no_points_for_mapping")}</p>
        ) : (
          <details>
            <summary>{t("web.registre.modbus_create_title")}</summary>
            <form action={createDeviceMapping} style={{ maxWidth: 400 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <input type="hidden" name="point_ids" value={points.map((point) => point.id).join(",")} />
              <label>
                {t("web.registre.modbus_host")}
                <input name="host" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.modbus_port")}
                <input name="port" type="number" defaultValue={502} required style={fieldStyle} />
              </label>
              {points.map((point) => (
                <label key={point.id} style={labelStyle}>
                  {point.name}
                  <select name={`register_${point.id}`} defaultValue="" style={fieldStyle}>
                    <option value="">{t("web.registre.modbus_register_none")}</option>
                    {SDM120_REGISTERS.map((register) => (
                      <option key={register} value={register}>
                        {t(`modbus_register.${register}`)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              <label style={labelStyle}>
                {t("web.registre.rule_reason")}
                <input name="reason" required style={fieldStyle} />
              </label>
              <button type="submit" style={submitStyle}>
                {t("web.registre.submit")}
              </button>
            </form>
          </details>
        ))}
      {canManage && points.length > 0 && (
        <details>
          <summary>{t("web.registre.modbus_create_test_relay_title")}</summary>
          <p style={mutedStyle}>{t("web.registre.modbus_test_relay_note")}</p>
          <form action={createSimulatedRelayMapping} style={{ maxWidth: 400 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <label>
              {t("web.registre.modbus_host")}
              <input name="host" required style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.modbus_port")}
              <input name="port" type="number" defaultValue={5021} required style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.modbus_test_relay_point_label")}
              <select name="point_id" required defaultValue="" style={fieldStyle}>
                <option value="" disabled>
                  {t("web.registre.modbus_register_none")}
                </option>
                {points.map((point) => (
                  <option key={point.id} value={point.id}>
                    {point.name}
                  </option>
                ))}
              </select>
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
      )}
    </>
  );
}

function BacnetMappingBlock({
  nodeId,
  points,
  versions,
  canManage,
  t,
}: {
  nodeId: string;
  points: { id: string; name: string }[];
  versions: BacnetMappingVersion[];
  canManage: boolean;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const pointName = (pointId: string) => points.find((p) => p.id === pointId)?.name ?? pointId;
  return (
    <>
      {versions.length === 0 && <p style={mutedStyle}>{t("web.registre.bacnet_mapping_none")}</p>}
      {versions.map((version) => (
        <div key={version.id} style={{ marginBottom: 12 }}>
          <p style={{ margin: 0 }}>
            {t("web.registre.rule_version", { version: String(version.version) })} —{" "}
            {t(`config_status.${version.status}`)} —{" "}
            {t("web.registre.bacnet_mapping_summary", { address: version.content.address })}
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
            {canManage && version.status === "retired" && (
              <form action={restoreRule} style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}>
                <input type="hidden" name="version_id" value={version.id} />
                <input type="hidden" name="node_id" value={nodeId} />
                <input name="reason" required placeholder={t("web.registre.restore_reason")} />
                <button type="submit">{t("web.registre.restore_rule")}</button>
              </form>
            )}
          </p>
          <p style={{ ...mutedStyle, margin: 0, marginLeft: 16 }}>
            {t("web.registre.modbus_points_title")} :{" "}
            {version.content.points
              .map((entry) => `${pointName(entry.point_id)} (${entry.object_type} #${entry.object_instance})`)
              .join(", ")}
          </p>
        </div>
      ))}
      {canManage &&
        (points.length === 0 ? (
          <p style={mutedStyle}>{t("web.registre.modbus_no_points_for_mapping")}</p>
        ) : (
          <details>
            <summary>{t("web.registre.bacnet_mapping_create_title")}</summary>
            <form action={createBacnetDeviceMapping} style={{ maxWidth: 420 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <input type="hidden" name="point_ids" value={points.map((point) => point.id).join(",")} />
              <label>
                {t("web.registre.bacnet_address_label")}
                <input name="address" required placeholder="192.168.1.50:47808" style={fieldStyle} />
              </label>
              {points.map((point) => (
                <div key={point.id} style={{ marginTop: 8 }}>
                  <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>{point.name}</p>
                  <label style={labelStyle}>
                    {t("web.registre.bacnet_mapping_object_type_label")}
                    <select name={`object_type_${point.id}`} defaultValue="" style={fieldStyle}>
                      <option value="">{t("web.registre.modbus_register_none")}</option>
                      {BACNET_DISCOVERABLE_OBJECT_TYPES.map((objectType) => (
                        <option key={objectType} value={objectType}>
                          {objectType}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={labelStyle}>
                    {t("web.registre.bacnet_mapping_object_instance_label")}
                    <input
                      name={`object_instance_${point.id}`}
                      type="number"
                      min={0}
                      defaultValue={0}
                      style={fieldStyle}
                    />
                  </label>
                  <label style={labelStyle}>
                    {t("web.registre.bacnet_mapping_property_label")}
                    <input
                      name={`property_${point.id}`}
                      defaultValue="present-value"
                      style={fieldStyle}
                    />
                  </label>
                </div>
              ))}
              <label style={labelStyle}>
                {t("web.registre.rule_reason")}
                <input name="reason" required style={fieldStyle} />
              </label>
              <button type="submit" style={submitStyle}>
                {t("web.registre.submit")}
              </button>
            </form>
          </details>
        ))}
    </>
  );
}

function BacnetDiscoveryBlock({
  nodeId,
  batches,
  selectedBatchId,
  proposals,
  canManage,
  locale,
  timeZone,
  t,
}: {
  nodeId: string;
  batches: BacnetDiscoveryBatch[];
  selectedBatchId: string | null;
  proposals: BacnetDiscoveryProposal[];
  canManage: boolean;
  locale: Locale;
  timeZone: string | null;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  return (
    <>
      {batches.length === 0 && <p style={mutedStyle}>{t("web.registre.bacnet_no_batch")}</p>}
      {batches.map((batch) => (
        <p key={batch.id} style={{ margin: "0 0 4px" }}>
          {formatDateTime(locale, batch.scanned_at, timeZone)} — {batch.address} —{" "}
          {t(`bacnet_batch_status.${batch.status}`)}
          {batch.status === "ready" &&
            ` — ${t("web.registre.bacnet_batch_counts", {
              proposals: String(batch.proposal_count ?? 0),
              duplicates: String(batch.duplicate_count ?? 0),
            })}`}
          {batch.status === "failed" &&
            batch.error_code &&
            ` — ${errorMessage(locale, batch.error_code) ?? batch.error_code}`}
          {" — "}
          <Link href={`/registre/${nodeId}?bacnet_batch=${batch.id}`}>
            {t("web.registre.bacnet_view_proposals")}
          </Link>
        </p>
      ))}

      {selectedBatchId && (
        <div style={{ marginTop: 12, marginLeft: 16 }}>
          <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>
            {t("web.registre.bacnet_proposals_title")}
          </p>
          {proposals.length === 0 && (
            <p style={mutedStyle}>{t("web.registre.bacnet_proposals_none")}</p>
          )}
          {proposals.map((proposal) => (
            <BacnetProposalRow
              key={proposal.id}
              proposal={proposal}
              nodeId={nodeId}
              batchId={selectedBatchId}
              canManage={canManage}
              locale={locale}
              t={t}
            />
          ))}
        </div>
      )}

      {canManage && (
        <details style={{ marginTop: 8 }}>
          <summary>{t("web.registre.bacnet_scan_title")}</summary>
          <form action={scanBacnetDevice} style={{ maxWidth: 360 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <label>
              {t("web.registre.bacnet_address_label")}
              <input name="address" required placeholder="192.168.1.50:47808" style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.bacnet_timeout_label")}
              <input
                name="timeout"
                type="number"
                min={0.5}
                max={15}
                step={0.5}
                defaultValue={3}
                style={fieldStyle}
              />
            </label>
            <button type="submit" style={submitStyle}>
              {t("web.registre.bacnet_scan_button")}
            </button>
          </form>
        </details>
      )}
    </>
  );
}

function BacnetProposalRow({
  proposal,
  nodeId,
  batchId,
  canManage,
  locale,
  t,
}: {
  proposal: BacnetDiscoveryProposal;
  nodeId: string;
  batchId: string;
  canManage: boolean;
  locale: Locale;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const objectLabel = `${proposal.object_type} #${proposal.object_instance}${
    proposal.object_name ? ` — ${proposal.object_name}` : ""
  }`;
  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ margin: 0 }}>
        <span style={strongStyle}>{objectLabel}</span> —{" "}
        {t(`bacnet_proposal_status.${proposal.status}`)}
      </p>
      <p style={{ ...mutedStyle, margin: 0 }}>
        {proposal.proposed_point_class
          ? t("web.registre.bacnet_proposed_class_label", {
              class: t(`point_class.${proposal.proposed_point_class}`),
            })
          : t("web.registre.bacnet_no_class_proposed")}
        {proposal.confidence !== null &&
          ` (${t("web.registre.bacnet_confidence_label", {
            percent: formatNumber(locale, Math.round(proposal.confidence * 100)),
          })})`}
      </p>
      <p style={{ ...mutedStyle, margin: 0 }}>{proposal.reason_message}</p>
      {proposal.present_value_preview !== null && (
        <p style={{ ...mutedStyle, margin: 0 }}>
          {t("web.registre.bacnet_value_preview_label", { value: proposal.present_value_preview })}
          {proposal.bacnet_units ? ` (${proposal.bacnet_units})` : ""}
        </p>
      )}
      {proposal.status === "rejected" && proposal.rejection_reason && (
        <p style={{ ...mutedStyle, margin: 0 }}>
          {t("web.registre.bacnet_rejected_reason", { reason: proposal.rejection_reason })}
        </p>
      )}
      {proposal.status === "accepted" && (
        <p style={{ ...mutedStyle, margin: 0 }}>{t("web.registre.bacnet_accepted_point")}</p>
      )}
      {canManage && proposal.status === "proposed" && (
        <div style={signalActionsStyle}>
          <details>
            <summary>{t("web.registre.bacnet_accept_button")}</summary>
            <form action={acceptBacnetProposal} style={{ maxWidth: 320 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <input type="hidden" name="batch_id" value={batchId} />
              <input type="hidden" name="proposal_id" value={proposal.id} />
              <label>
                {t("web.registre.bacnet_class_override_label")}
                <input
                  name="point_class"
                  defaultValue={proposal.proposed_point_class ?? ""}
                  style={fieldStyle}
                />
              </label>
              <label style={labelStyle}>
                {t("web.registre.bacnet_unit_override_label")}
                <input
                  name="unit"
                  defaultValue={proposal.proposed_unit ?? ""}
                  style={fieldStyle}
                />
              </label>
              <label style={labelStyle}>
                {t("web.registre.bacnet_name_override_label")}
                <input
                  name="name"
                  defaultValue={proposal.object_name ?? ""}
                  style={fieldStyle}
                />
              </label>
              <button type="submit" style={submitStyle}>
                {t("web.registre.bacnet_accept_confirm")}
              </button>
            </form>
          </details>
          <form action={rejectBacnetProposal} style={{ display: "inline-flex", gap: 4 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <input type="hidden" name="batch_id" value={batchId} />
            <input type="hidden" name="proposal_id" value={proposal.id} />
            <input name="reason" required placeholder={t("web.registre.bacnet_reject_reason_label")} />
            <button type="submit">{t("web.registre.bacnet_reject_button")}</button>
          </form>
        </div>
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

function CommandBlock({
  nodeId,
  points,
  relayPointId,
  lastCommand,
  scheduledCommands,
  activeControlMode,
  controlModeVersions,
  automationRuleVersions,
  commandPolicyVersions,
  canSendCommand,
  canManage,
  locale,
  timeZone,
  t,
}: {
  nodeId: string;
  points: { id: string; name: string; value_type: string }[];
  relayPointId: string | null;
  lastCommand: PassportCommand | null;
  scheduledCommands: ScheduledCommand[];
  activeControlMode: "manual" | "automatic";
  controlModeVersions: PointControlModeVersion[];
  automationRuleVersions: AutomationRuleVersion[];
  commandPolicyVersions: CommandPointPolicyVersion[];
  canSendCommand: boolean;
  canManage: boolean;
  locale: Locale;
  timeZone: string | null;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  if (!relayPointId) {
    return <p style={mutedStyle}>{t("web.registre.modbus_no_mapping")}</p>;
  }
  const pointName = points.find((point) => point.id === relayPointId)?.name ?? relayPointId;
  const numericPoints = points.filter((point) => point.value_type === "number");
  const draftModeVersion = controlModeVersions.find((version) => version.status === "draft");
  return (
    <div>
      <p style={{ margin: 0 }}>{pointName}</p>
      <div style={{ marginTop: 8 }}>
        <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>
          {t("web.registre.control_mode_title")}
        </p>
        <p style={{ margin: 0 }}>
          {t(`control_mode.${activeControlMode}`)} — {t(`web.registre.control_mode_explanation.${activeControlMode}`)}
        </p>
        {draftModeVersion && (
          <p style={{ margin: 0 }}>
            {t("web.registre.control_mode_draft_pending", {
              mode: t(`control_mode.${draftModeVersion.content.mode}`),
            })}
            {canManage && (
              <form action={activateRule} style={{ display: "inline", marginLeft: 8 }}>
                <input type="hidden" name="version_id" value={draftModeVersion.id} />
                <input type="hidden" name="node_id" value={nodeId} />
                <button type="submit">{t("web.registre.activate_rule")}</button>
              </form>
            )}
          </p>
        )}
        {canManage && !draftModeVersion && (
          <details>
            <summary>{t("web.registre.control_mode_propose")}</summary>
            <form action={createPointControlMode} style={{ maxWidth: 360 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <input type="hidden" name="point_id" value={relayPointId} />
              <label style={labelStyle}>
                {t("web.registre.control_mode_label")}
                <select
                  name="mode"
                  defaultValue={activeControlMode === "automatic" ? "manual" : "automatic"}
                  style={fieldStyle}
                >
                  <option value="manual">{t("control_mode.manual")}</option>
                  <option value="automatic">{t("control_mode.automatic")}</option>
                </select>
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
        )}
      </div>
      {canSendCommand && (
        <div style={signalActionsStyle}>
          <form action={sendTestCommand}>
            <input type="hidden" name="node_id" value={nodeId} />
            <input type="hidden" name="point_id" value={relayPointId} />
            <input type="hidden" name="requested_value" value="1" />
            <button type="submit">{t("web.registre.command_turn_on")}</button>
          </form>
          <form action={sendTestCommand}>
            <input type="hidden" name="node_id" value={nodeId} />
            <input type="hidden" name="point_id" value={relayPointId} />
            <input type="hidden" name="requested_value" value="0" />
            <button type="submit">{t("web.registre.command_turn_off")}</button>
          </form>
        </div>
      )}
      {canSendCommand && (
        <form
          action={scheduleTestCommand}
          style={{ display: "flex", alignItems: "flex-end", gap: 8, flexWrap: "wrap", marginTop: 12 }}
        >
          <input type="hidden" name="node_id" value={nodeId} />
          <input type="hidden" name="point_id" value={relayPointId} />
          <div>
            <label style={{ ...labelStyle, marginTop: 0 }}>
              {t("web.registre.scheduled_command_value_label")}
            </label>
            <select name="requested_value" style={fieldStyle} defaultValue="1">
              <option value="1">{t("web.registre.command_turn_on")}</option>
              <option value="0">{t("web.registre.command_turn_off")}</option>
            </select>
          </div>
          <div>
            <label style={{ ...labelStyle, marginTop: 0 }}>
              {t("web.registre.scheduled_command_when_label")}
            </label>
            <input type="datetime-local" name="scheduled_for" required style={fieldStyle} />
          </div>
          <button type="submit">{t("web.registre.scheduled_command_submit")}</button>
        </form>
      )}
      {scheduledCommands.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>
            {t("web.registre.scheduled_command_list_title")}
          </p>
          <ul style={{ listStyle: "none", padding: 0, margin: "4px 0 0" }}>
            {scheduledCommands.map((scheduled) => (
              <li
                key={scheduled.id}
                style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}
              >
                <span>
                  {t(`scheduled_command_status.${scheduled.status}`)} —{" "}
                  {t("web.registre.command_requested_value", {
                    value: formatNumber(locale, scheduled.requested_value),
                  })}{" "}
                  —{" "}
                  {t("web.registre.scheduled_command_for", {
                    when: formatDateTime(locale, scheduled.scheduled_for, timeZone),
                  })}
                  {scheduled.failure_reason &&
                    ` — ${t("web.registre.command_failure_reason", {
                      reason: t(`command_failure_reason.${scheduled.failure_reason}`),
                    })}`}
                </span>
                {scheduled.status === "pending" && canSendCommand && (
                  <form action={cancelScheduledTestCommand}>
                    <input type="hidden" name="node_id" value={nodeId} />
                    <input type="hidden" name="scheduled_command_id" value={scheduled.id} />
                    <button type="submit">{t("web.registre.scheduled_command_cancel")}</button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div style={{ marginTop: 8 }}>
        <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>
          {t("web.registre.command_last_title")}
        </p>
        {lastCommand ? (
          <>
            <p style={{ margin: 0 }}>
              {t(`command_status.${lastCommand.status}`)} —{" "}
              {t("web.registre.command_requested_value", {
                value: formatNumber(locale, lastCommand.requested_value),
              })}
              {lastCommand.actual_value !== null &&
                ` — ${t("web.registre.command_actual_value", {
                  value: formatNumber(locale, lastCommand.actual_value),
                })}`}
            </p>
            {lastCommand.failure_reason && (
              <p style={{ margin: 0 }}>
                {t("web.registre.command_failure_reason", {
                  reason: t(`command_failure_reason.${lastCommand.failure_reason}`),
                })}
              </p>
            )}
            <p style={mutedStyle}>
              {t("web.registre.command_at", {
                when: formatDateTime(locale, lastCommand.created_at, timeZone),
              })}
            </p>
          </>
        ) : (
          <p style={mutedStyle}>{t("web.registre.command_no_command")}</p>
        )}
      </div>
      <div style={{ marginTop: 12 }}>
        <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>
          {t("web.registre.automation_rules_title")}
        </p>
        {automationRuleVersions.length === 0 && (
          <p style={mutedStyle}>{t("web.registre.no_automation_rules")}</p>
        )}
        {automationRuleVersions.map((version) => {
          const triggerPointName =
            points.find((point) => point.id === version.content.trigger_point_id)?.name ??
            version.content.trigger_point_id;
          return (
            <p key={version.id} style={{ margin: 0 }}>
              {t("web.registre.rule_version", { version: String(version.version) })} —{" "}
              {t(`config_status.${version.status}`)} — {version.content.title} ({triggerPointName}{" "}
              {version.content.operator === ">"
                ? t("web.registre.rule_operator_gt")
                : t("web.registre.rule_operator_lt")}{" "}
              {version.content.threshold} →{" "}
              {t("web.registre.command_requested_value", {
                value: formatNumber(locale, version.content.requested_value),
              })}
              )
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
              {canManage && version.status === "retired" && (
                <form action={restoreRule} style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}>
                  <input type="hidden" name="version_id" value={version.id} />
                  <input type="hidden" name="node_id" value={nodeId} />
                  <input name="reason" required placeholder={t("web.registre.restore_reason")} />
                  <button type="submit">{t("web.registre.restore_rule")}</button>
                </form>
              )}
            </p>
          );
        })}
        {canManage && (
          <details>
            <summary>{t("web.registre.create_automation_rule")}</summary>
            <form action={createAutomationRule} style={{ maxWidth: 360 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <input type="hidden" name="target_point_id" value={relayPointId} />
              <label>
                {t("web.registre.rule_title")}
                <input name="title" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.automation_rule_trigger_point")}
                <select name="trigger_point_id" required style={fieldStyle}>
                  {numericPoints.map((point) => (
                    <option key={point.id} value={point.id}>
                      {point.name}
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
                {t("web.registre.automation_rule_requested_value")}
                <input name="requested_value" type="number" step="any" required style={fieldStyle} />
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
        )}
      </div>
      <CommandPolicyBlock
        nodeId={nodeId}
        pointId={relayPointId}
        versions={commandPolicyVersions}
        canManage={canManage}
        t={t}
      />
    </div>
  );
}

/**
 * Policy de commande (V2, priorité « autorisation/policies »,
 * app.command_policies) : restreint, pour ce point précis, les rôles et les
 * valeurs acceptés par une commande immédiate, planifiée ou automatisée —
 * au-delà des rôles globaux déjà vérifiés par /commands. Même mécanisme
 * de configuration versionnée que le mode du point et les règles
 * d'automatisation ci-dessus, approbation à une seule personne (une policy
 * ne peut que restreindre davantage, jamais étendre — voir
 * app/command_policies.py).
 */
function CommandPolicyBlock({
  nodeId,
  pointId,
  versions,
  canManage,
  t,
}: {
  nodeId: string;
  pointId: string;
  versions: CommandPointPolicyVersion[];
  canManage: boolean;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const activePolicy = versions.find((version) => version.status === "active") ?? null;
  const draftPolicy = versions.find((version) => version.status === "draft") ?? null;

  function describePolicy(content: CommandPointPolicyVersion["content"]): string {
    const parts: string[] = [];
    if (content.allowed_roles) {
      parts.push(
        t("web.registre.command_policy_roles_summary", {
          roles: content.allowed_roles.map((role) => t(`role.${role}`)).join(", "),
        }),
      );
    }
    if (content.allowed_values) {
      parts.push(
        t("web.registre.command_policy_values_summary", {
          values: content.allowed_values.join(", "),
        }),
      );
    }
    return parts.length > 0 ? parts.join(" — ") : t("web.registre.command_policy_none");
  }

  return (
    <div style={{ marginTop: 12 }}>
      <p style={{ ...mutedStyle, margin: 0, fontWeight: 600 }}>
        {t("web.registre.command_policy_title")}
      </p>
      <p style={{ margin: 0 }}>
        {activePolicy ? describePolicy(activePolicy.content) : t("web.registre.command_policy_none")}
      </p>
      {draftPolicy && (
        <p style={{ margin: 0 }}>
          {t("web.registre.command_policy_draft_pending", { summary: describePolicy(draftPolicy.content) })}
          {canManage && (
            <form action={activateRule} style={{ display: "inline", marginLeft: 8 }}>
              <input type="hidden" name="version_id" value={draftPolicy.id} />
              <input type="hidden" name="node_id" value={nodeId} />
              <button type="submit">{t("web.registre.activate_rule")}</button>
            </form>
          )}
        </p>
      )}
      {canManage && !draftPolicy && (
        <details>
          <summary>{t("web.registre.command_policy_propose")}</summary>
          <form action={createCommandPolicy} style={{ maxWidth: 360 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <input type="hidden" name="point_id" value={pointId} />
            <fieldset style={{ border: "none", padding: 0, marginTop: 12 }}>
              <legend style={{ fontWeight: 600 }}>{t("web.registre.command_policy_roles_label")}</legend>
              {COMMAND_ROLES.map((role) => (
                <label key={role} style={{ display: "block" }}>
                  <input type="checkbox" name="allowed_roles" value={role} /> {t(`role.${role}`)}
                </label>
              ))}
            </fieldset>
            <label style={labelStyle}>
              {t("web.registre.command_policy_values_label")}
              <input
                name="allowed_values"
                placeholder={t("web.registre.command_policy_values_placeholder")}
                style={fieldStyle}
              />
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
      )}
      {activePolicy && canManage && (
        <form action={retireRule} style={{ marginTop: 4, display: "inline-flex", gap: 4 }}>
          <input type="hidden" name="version_id" value={activePolicy.id} />
          <input type="hidden" name="node_id" value={nodeId} />
          <input name="reason" required placeholder={t("web.registre.retire_reason")} />
          <button type="submit">{t("web.registre.command_policy_remove")}</button>
        </form>
      )}
    </div>
  );
}

function EnergyBlock({
  results,
  comparison,
  activeBaseline,
  nodeId,
  canManage,
  locale,
  timeZone,
  t,
}: {
  results: EnergyNormalizedResult[];
  comparison: EnergyComparison | null;
  activeBaseline: EnergyBaselineVersion | null;
  nodeId: string;
  canManage: boolean;
  locale: Locale;
  timeZone: string | null;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const latest = results[0] ?? null;
  // Plus ancienne d'abord, pour une lecture gauche → droite chronologique
  // (`results` arrive trié du plus récent au plus ancien, voir `latest`
  // ci-dessus) ; bornée aux 12 dernières périodes, jamais un historique
  // complet chargé dans un graphique.
  const chartPeriods: EnergyChartPeriod[] = results
    .slice(0, 12)
    .slice()
    .reverse()
    .map((result) => ({
      label: formatDate(locale, result.period_start, null),
      raw: result.raw_consumption,
      normalized: result.normalization_status === "ok" ? result.normalized_consumption : null,
    }));
  return (
    <div>
      {chartPeriods.length > 1 && (
        <div style={{ marginBottom: 12 }}>
          <p style={{ ...mutedStyle, fontWeight: 600, marginBottom: 4 }}>
            {t("web.registre.energy_chart_title")}
          </p>
          <EnergyBarChart
            periods={chartPeriods}
            unit={latest?.raw_consumption_unit ?? ""}
            rawLabel={t("web.registre.energy_chart_raw_legend")}
            normalizedLabel={t("web.registre.energy_chart_normalized_legend")}
          />
        </div>
      )}
      {latest ? (
        <>
          <p style={{ margin: 0 }}>
            {t("web.registre.energy_period", {
              start: formatDate(locale, latest.period_start, null),
              end: formatDate(locale, latest.period_end, null),
            })}
          </p>
          <p style={{ margin: 0 }}>
            {t("web.registre.energy_raw_consumption", {
              value: formatNumber(locale, latest.raw_consumption),
              unit: latest.raw_consumption_unit,
            })}
          </p>
          {latest.normalization_status === "ok" && latest.normalized_consumption !== null ? (
            <p style={{ margin: 0 }}>
              {t("web.registre.energy_normalized_consumption", {
                value: formatNumber(locale, latest.normalized_consumption),
                unit: latest.raw_consumption_unit,
              })}
            </p>
          ) : (
            <p style={mutedStyle}>{t(`web.registre.energy_status_${latest.normalization_status}`)}</p>
          )}
          {latest.estimated_cost ? (
            <>
              <p style={{ margin: 0 }}>
                {t("web.registre.energy_estimated_cost", {
                  value: formatCurrency(
                    locale,
                    latest.estimated_cost.amount,
                    latest.estimated_cost.currency,
                  ),
                })}
              </p>
              <p style={mutedStyle}>{t("web.registre.energy_estimated_cost_note")}</p>
            </>
          ) : (
            <p style={mutedStyle}>{t("web.registre.energy_estimated_cost_unavailable")}</p>
          )}
          {comparison &&
            (comparison.comparable && comparison.percent_deviation !== null ? (
              <p style={{ margin: 0 }}>
                {t(
                  comparison.reduced
                    ? "web.registre.energy_comparison_reduced"
                    : "web.registre.energy_comparison_increased",
                  { percent: formatNumber(locale, Math.abs(comparison.percent_deviation)) },
                )}
              </p>
            ) : (
              <p style={mutedStyle}>{t("web.registre.energy_comparison_unavailable")}</p>
            ))}
          <p style={mutedStyle}>
            {t("web.registre.energy_computed_at", {
              when: formatDateTime(locale, latest.computed_at, timeZone),
            })}
          </p>
        </>
      ) : (
        <p style={mutedStyle}>{t("web.registre.energy_no_result")}</p>
      )}
      {canManage && activeBaseline && (
        <details style={{ marginTop: 8 }}>
          <summary>{t("web.registre.energy_baseline_compute_title")}</summary>
          <form action={computeEnergyResult} style={{ maxWidth: 360 }}>
            <input type="hidden" name="node_id" value={nodeId} />
            <input type="hidden" name="baseline_config_version_id" value={activeBaseline.id} />
            <label>
              {t("web.registre.energy_baseline_compute_period_start")}
              <input name="period_start" type="date" required style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.registre.energy_baseline_compute_period_end")}
              <input name="period_end" type="date" required style={fieldStyle} />
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

function EnergyBaselineBlock({
  nodeId,
  points,
  versions,
  canManage,
  locale,
  t,
}: {
  nodeId: string;
  points: { id: string; name: string }[];
  versions: EnergyBaselineVersion[];
  canManage: boolean;
  locale: Locale;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const pointName = (pointId: string) => points.find((p) => p.id === pointId)?.name ?? pointId;
  return (
    <>
      {versions.length === 0 && <p style={mutedStyle}>{t("web.registre.energy_baseline_no_version")}</p>}
      {versions.map((version) => (
        <div key={version.id} style={{ marginBottom: 12 }}>
          <p style={{ margin: 0 }}>
            {t("web.registre.rule_version", { version: String(version.version) })} —{" "}
            {t(`config_status.${version.status}`)}
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
            {canManage && version.status === "retired" && (
              <form action={restoreRule} style={{ display: "inline-flex", gap: 4, marginLeft: 8 }}>
                <input type="hidden" name="version_id" value={version.id} />
                <input type="hidden" name="node_id" value={nodeId} />
                <input name="reason" required placeholder={t("web.registre.restore_reason")} />
                <button type="submit">{t("web.registre.restore_rule")}</button>
              </form>
            )}
          </p>
          <p style={{ ...mutedStyle, margin: 0, marginLeft: 16 }}>
            {t("web.registre.energy_baseline_summary", {
              point: pointName(version.content.point_id),
              kind: t(`degree_day_kind.${version.content.degree_day_kind}`),
              base: formatNumber(locale, version.content.degree_day_base_temperature_celsius),
              start: formatDate(locale, version.content.reference_period.start, null),
              end: formatDate(locale, version.content.reference_period.end, null),
            })}
          </p>
        </div>
      ))}
      {canManage &&
        (points.length === 0 ? (
          <p style={mutedStyle}>{t("web.registre.modbus_no_points_for_mapping")}</p>
        ) : (
          <details>
            <summary>{t("web.registre.energy_baseline_create_title")}</summary>
            <form action={createEnergyBaseline} style={{ maxWidth: 360 }}>
              <input type="hidden" name="node_id" value={nodeId} />
              <label>
                {t("web.registre.energy_baseline_point_label")}
                <select name="point_id" required defaultValue="" style={fieldStyle}>
                  <option value="" disabled>
                    {t("web.registre.modbus_register_none")}
                  </option>
                  {points.map((point) => (
                    <option key={point.id} value={point.id}>
                      {point.name}
                    </option>
                  ))}
                </select>
              </label>
              <label style={labelStyle}>
                {t("web.registre.energy_baseline_reference_start")}
                <input name="reference_start" type="date" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.energy_baseline_reference_end")}
                <input name="reference_end" type="date" required style={fieldStyle} />
              </label>
              <label style={labelStyle}>
                {t("web.registre.energy_baseline_base_temperature")}
                <input
                  name="base_temperature"
                  type="number"
                  step="any"
                  defaultValue={18}
                  required
                  style={fieldStyle}
                />
              </label>
              <label style={labelStyle}>
                {t("web.registre.energy_baseline_kind_label")}
                <select name="degree_day_kind" defaultValue="heating" style={fieldStyle}>
                  <option value="heating">{t("degree_day_kind.heating")}</option>
                  <option value="cooling">{t("degree_day_kind.cooling")}</option>
                </select>
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
        ))}
    </>
  );
}
