import { useEffect, useRef, useState } from "react";
import { type BarcodeScanningResult, CameraView, useCameraPermissions } from "expo-camera";
import {
  ActivityIndicator,
  Button,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { locale, t } from "../src/lib/i18n";
import { formatDate, formatDateTime, formatNumber } from "../src/i18n/translator";
import {
  type EquipmentStatus,
  type Passport,
  type PassportCommand,
  type PassportUnit,
  type ScanResult,
  type ScheduledCommand,
  type TimelineEntry,
  fetchControlMode,
  fetchPassportById,
  fetchPassportByTag,
  fetchScheduledCommands,
  fetchSimulatedRelayPointId,
  fetchTimeline,
  isPlatformTag,
  parseTagCode,
  sendCommand,
  statusMessage,
} from "../src/lib/passport";
import { colors, equipmentStatusToAssetStatus } from "../src/design/colors";
import { AssetStatusBadge, SeverityBadge } from "../src/design/StatusBadge";
import { Text } from "../src/design/Text";

/**
 * Lecture de l'étiquette par l'appareil photo, ou saisie du code imprimé sous
 * le QR (même vérification dans les deux cas : `parseTagCode`). Le QR ne
 * contient qu'un code opaque ; tout le contenu vient du serveur, selon les
 * droits de la personne connectée.
 *
 * Deuxième point d'entrée (06/10/2026) : arrivée depuis une liste qui connaît
 * déjà l'identifiant de l'équipement (Actifs, Alertes) — `fetchPassportById`
 * charge alors le même passeport directement, sans étiquette à scanner.
 */
interface LookupFn {
  (): Promise<ScanResult>;
}

export default function PasseportScreen() {
  const auth = useAuth();
  const params = useLocalSearchParams<{ functionalLocationId?: string }>();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [passport, setPassport] = useState<Passport | null>(null);
  const [relayPointId, setRelayPointId] = useState<string | null>(null);
  const [controlMode, setControlMode] = useState<"manual" | "automatic">("manual");
  const [scheduledCommands, setScheduledCommands] = useState<ScheduledCommand[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  // Un QR reste devant l'objectif plusieurs images de suite : une seule lecture.
  const handled = useRef(false);
  // Retenu pour rafraîchir le passeport après l'envoi d'une commande, sans
  // redemander une étiquette ni un identifiant à la personne.
  const lastLookup = useRef<LookupFn | null>(null);

  async function _applyResult(result: ScanResult, token: string) {
    if (result.ok) {
      setPassport(result.passport);
      if (result.passport.node_type === "functional_location") {
        const pointId = await fetchSimulatedRelayPointId(
          config.apiUrl,
          token,
          result.passport.node_id,
        );
        setRelayPointId(pointId);
        if (pointId) {
          const [mode, scheduled] = await Promise.all([
            fetchControlMode(config.apiUrl, token, pointId),
            fetchScheduledCommands(config.apiUrl, token, pointId),
          ]);
          setControlMode(mode);
          setScheduledCommands(scheduled);
        } else {
          setControlMode("manual");
          setScheduledCommands([]);
        }
      }
      setTimeline(await fetchTimeline(config.apiUrl, token, result.passport.node_id));
    } else {
      setMessage(t(result.messageKey, result.params));
    }
  }

  async function lookUp(raw: string) {
    setPassport(null);
    setRelayPointId(null);
    setControlMode("manual");
    setScheduledCommands([]);
    setTimeline([]);
    const code = parseTagCode(raw);
    if (!code) {
      setMessage(t("mobile.passport.invalid_code"));
      return;
    }
    const token = await auth.getAccessToken();
    if (!token) {
      setMessage(t("mobile.passport.sign_in_first"));
      return;
    }
    setLoading(true);
    setMessage(null);
    const fetchResult = () => fetchPassportByTag(config.apiUrl, token, code, locale);
    lastLookup.current = fetchResult;
    await _applyResult(await fetchResult(), token);
    setLoading(false);
  }

  async function lookUpById(nodeId: string) {
    setPassport(null);
    setRelayPointId(null);
    setControlMode("manual");
    setScheduledCommands([]);
    setTimeline([]);
    const token = await auth.getAccessToken();
    if (!token) {
      setMessage(t("mobile.passport.sign_in_first"));
      return;
    }
    setLoading(true);
    setMessage(null);
    const fetchResult = () => fetchPassportById(config.apiUrl, token, nodeId, locale);
    lastLookup.current = fetchResult;
    await _applyResult(await fetchResult(), token);
    setLoading(false);
  }

  // Arrivée depuis une liste (Actifs, Alertes) : charge directement, sans
  // attendre un scan ou une saisie manuelle.
  useEffect(() => {
    if (params.functionalLocationId) {
      void lookUpById(params.functionalLocationId);
    }
  }, [params.functionalLocationId]);

  async function loadOlderTimeline() {
    if (!passport || timeline.length === 0) return;
    const token = await auth.getAccessToken();
    if (!token) return;
    setTimelineLoading(true);
    const older = await fetchTimeline(
      config.apiUrl,
      token,
      passport.node_id,
      timeline[timeline.length - 1].at,
    );
    setTimeline([...timeline, ...older]);
    setTimelineLoading(false);
  }

  async function sendTestCommand(pointId: string, requestedValue: number) {
    const token = await auth.getAccessToken();
    if (!token) {
      setMessage(t("mobile.passport.sign_in_first"));
      return;
    }
    setLoading(true);
    setMessage(null);
    const result = await sendCommand(config.apiUrl, token, pointId, requestedValue);
    if (!result.ok) {
      setMessage(t(result.messageKey, result.params));
      setLoading(false);
      return;
    }
    // Rejoue la même lecture (étiquette ou identifiant direct) pour
    // afficher l'état à jour de la commande.
    if (lastLookup.current) {
      await _applyResult(await lastLookup.current(), token);
    }
    setLoading(false);
  }

  async function startScan() {
    setMessage(null);
    const granted = permission?.granted || (await requestPermission()).granted;
    if (!granted) {
      setMessage(t("mobile.passport.camera_denied"));
      return;
    }
    handled.current = false;
    setScanning(true);
  }

  function onScanned({ data }: BarcodeScanningResult) {
    if (handled.current) return;
    handled.current = true;
    setScanning(false);
    if (!isPlatformTag(data)) {
      setMessage(t("mobile.passport.foreign_qr"));
      return;
    }
    setInput(data);
    void lookUp(data);
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {scanning ? (
        <View style={styles.scanner}>
          <CameraView
            style={styles.camera}
            facing="back"
            barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
            onBarcodeScanned={onScanned}
          />
          <Text style={styles.muted}>{t("mobile.passport.scan_hint")}</Text>
          <Button title={t("mobile.passport.scan_cancel")} onPress={() => setScanning(false)} />
        </View>
      ) : (
        <Button title={t("mobile.passport.scan")} onPress={startScan} disabled={loading} />
      )}
      <Text style={styles.label}>{t("mobile.passport.tag_code")}</Text>
      <TextInput
        style={styles.input}
        value={input}
        onChangeText={setInput}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder={t("mobile.passport.tag_placeholder")}
        placeholderTextColor={colors.textMuted}
      />
      <Button title={t("mobile.passport.show")} onPress={() => lookUp(input)} disabled={loading} />
      {loading && <ActivityIndicator />}
      {message && <Text style={styles.error}>{message}</Text>}
      {passport && (
        <PassportView
          passport={passport}
          relayPointId={relayPointId}
          controlMode={controlMode}
          scheduledCommands={scheduledCommands}
          onSendCommand={sendTestCommand}
          sending={loading}
          timeline={timeline}
          onLoadOlderTimeline={loadOlderTimeline}
          timelineLoading={timelineLoading}
        />
      )}
    </ScrollView>
  );
}

function PassportView({
  passport,
  relayPointId,
  controlMode,
  scheduledCommands,
  onSendCommand,
  sending,
  timeline,
  onLoadOlderTimeline,
  timelineLoading,
}: {
  passport: Passport;
  relayPointId: string | null;
  controlMode: "manual" | "automatic";
  scheduledCommands: ScheduledCommand[];
  onSendCommand: (pointId: string, requestedValue: number) => void;
  sending: boolean;
  timeline: TimelineEntry[];
  onLoadOlderTimeline: () => void;
  timelineLoading: boolean;
}) {
  const router = useRouter();
  const unit = passport.physical_unit ?? passport.current_unit ?? null;
  // Heures du site dans son fuseau quand il est renseigné, sinon celles de
  // l'appareil, et on le dit (ADR 013 : ne jamais laisser croire).
  const timeZone = passport.site?.timezone ?? null;
  const alarms = passport.open_alarms ?? [];
  return (
    <View style={styles.passport}>
      {passport.functional_location && (
        <Section title={t("mobile.passport.equipment")}>
          <Text style={styles.strong}>
            {passport.functional_location.code} — {passport.functional_location.name}
          </Text>
        </Section>
      )}
      {(passport.site?.name || (passport.space_path && passport.space_path.length > 0)) && (
        <Text style={styles.muted}>
          {[passport.site?.name, ...(passport.space_path ?? []).map((s) => s.name)]
            .filter(Boolean)
            .join(" › ")}
        </Text>
      )}

      {passport.status && (
        <Section title={t("mobile.passport.status")}>
          <StatusLine status={passport.status} timeZone={timeZone} />
        </Section>
      )}

      <Section title={t("mobile.passport.unit")}>
        {unit ? <UnitView unit={unit} /> : <Text>{t("mobile.passport.no_unit")}</Text>}
      </Section>

      {passport.points && passport.points.length > 0 && (
        <Section title={t("mobile.passport.latest")}>
          {passport.points.map((point) => (
            <Text key={point.id}>
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
            </Text>
          ))}
        </Section>
      )}

      {relayPointId && (
        <Section title={t("web.registre.command_section_title")}>
          <CommandSection
            points={passport.points ?? []}
            relayPointId={relayPointId}
            controlMode={controlMode}
            scheduledCommands={scheduledCommands}
            onSendCommand={onSendCommand}
            sending={sending}
            timeZone={timeZone}
          />
        </Section>
      )}

      <Section title={t("mobile.passport.signals")}>
        {alarms.map((alarm) => (
          <View key={alarm.id} style={styles.signalRow}>
            <SeverityBadge severity={alarm.severity} label={t(`severity.${alarm.severity}`)} />
            <View style={styles.signalText}>
              <Text style={styles.strong}>{t("mobile.passport.alarm")}</Text>
              <Text>{alarm.message}</Text>
              <Text style={styles.muted}>
                {t(`condition_state.${alarm.condition_state}`)} ·{" "}
                {t(`ack_state.${alarm.ack_state}`)}
              </Text>
            </View>
          </View>
        ))}
        {passport.open_findings.map((finding) => (
          <View key={finding.id} style={styles.signalRow}>
            <SeverityBadge severity={finding.severity} label={t(`severity.${finding.severity}`)} />
            <View style={styles.signalText}>
              <Text style={styles.strong}>{t("mobile.passport.finding")}</Text>
              <Text>{finding.title}</Text>
              <Text style={styles.muted}>
                {t(`certainty.${finding.certainty}`)}
                {finding.confidence !== null &&
                  ` (${t("mobile.passport.finding_confidence", {
                    percent: formatNumber(locale, Math.round(finding.confidence * 100)),
                  })})`}{" "}
                · {t(`condition_state.${finding.condition_state}`)}
              </Text>
            </View>
          </View>
        ))}
        {alarms.length === 0 && passport.open_findings.length === 0 && (
          <Text>{t("mobile.passport.nothing_open")}</Text>
        )}
      </Section>

      {passport.open_work_orders && passport.open_work_orders.length > 0 && (
        <Section title={t("mobile.passport.work_orders")}>
          {passport.open_work_orders.map((order) => (
            <Pressable
              key={order.id}
              onPress={() =>
                router.push({
                  pathname: "/nouvelle-intervention",
                  params: {
                    workOrderId: order.id,
                    workOrderTitle: order.title,
                    ...(passport.node_type === "functional_location"
                      ? { functionalLocationId: passport.node_id }
                      : {}),
                  },
                })
              }
            >
              <Text style={styles.workOrderLink}>
                {order.title} ({t(`work_order.status.${order.status}`)}) —{" "}
                {t("mobile.passport.work_order_create_intervention")}
              </Text>
            </Pressable>
          ))}
        </Section>
      )}

      {passport.recent_interventions && passport.recent_interventions.length > 0 && (
        <Section title={t("mobile.passport.interventions")}>
          {passport.recent_interventions.map((item) => (
            <Text key={item.id}>
              {formatDate(locale, item.started_at, timeZone)} —{" "}
              {item.action_label ?? item.summary ?? t("mobile.passport.no_summary")}
              {item.symptom_label ? ` (${item.symptom_label})` : ""}
            </Text>
          ))}
        </Section>
      )}

      <Section title={t("timeline.title")}>
        <TimelineView
          entries={timeline}
          timeZone={timeZone}
          onLoadOlder={onLoadOlderTimeline}
          loading={timelineLoading}
        />
      </Section>

      <Text style={styles.muted}>
        {timeZone
          ? t("mobile.passport.site_time", { timezone: timeZone })
          : t("mobile.passport.device_time")}
      </Text>
    </View>
  );
}

// Catalogue à utiliser pour traduire `status` selon le `field` d'une entrée —
// même liste que apps/web/src/components/Timeline.tsx, jamais une nouvelle
// traduction inventée pour la chronologie.
const TIMELINE_STATUS_CATALOG: Record<string, string> = {
  lifecycle_state: "lifecycle",
  handling_status: "handling_status",
  condition_state: "condition_state",
  ack_state: "ack_state",
  certainty: "certainty",
  intervention_type: "intervention_type",
};

function timelineStatusLabel(entry: TimelineEntry): string | null {
  if (!entry.status) return null;
  if (entry.kind === "event") {
    // Le titre de l'événement contient déjà tout ce qu'il y a à dire ;
    // `status` ne porte que le code stable, jamais affiché brut (ADR 013).
    return null;
  }
  if (entry.kind === "work_order" && entry.field === "status") {
    return t(`work_order.status.${entry.status}`);
  }
  const catalog = entry.field ? TIMELINE_STATUS_CATALOG[entry.field] : undefined;
  return catalog ? t(`${catalog}.${entry.status}`) : entry.status;
}

/**
 * Chronologie fusionnée de l'équipement (même donnée et même comportement
 * que le composant web partagé, apps/web/src/components/Timeline.tsx) :
 * interventions, ordres de travail, alarmes, constats, changements de
 * cycle de vie et, depuis le 02/10/2026, le journal système (hors ligne/en
 * ligne, donnée périmée/rétablie, cycle de vie d'une commande), dans un
 * seul historique ordonné par date.
 */
function TimelineView({
  entries,
  timeZone,
  onLoadOlder,
  loading,
}: {
  entries: TimelineEntry[];
  timeZone: string | null;
  onLoadOlder: () => void;
  loading: boolean;
}) {
  if (entries.length === 0) {
    return <Text style={styles.muted}>{t("timeline.empty")}</Text>;
  }
  return (
    <View style={{ gap: 6 }}>
      {entries.map((entry) => {
        const status = timelineStatusLabel(entry);
        return (
          <Text key={`${entry.kind}-${entry.reference_id}-${entry.at}`}>
            <Text style={styles.muted}>{formatDateTime(locale, entry.at, timeZone)}</Text>
            {" — "}
            <Text style={styles.strong}>{t(`timeline.kind_${entry.kind}`)}</Text>
            {entry.title && ` — ${entry.title}`}
            {!entry.title && status && ` — ${status}`}
            {entry.title && status && ` (${status})`}
            {entry.changed_by && ` — ${t("timeline.by", { actor: entry.changed_by })}`}
            {entry.note && `\n${entry.note}`}
          </Text>
        );
      })}
      {entries.length === 20 && (
        <Button title={t("timeline.load_older")} onPress={onLoadOlder} disabled={loading} />
      )}
    </View>
  );
}

/**
 * Boutons ON/OFF de test contre l'appareil explicitement simulé (exception
 * scopée à la règle non négociable 1, voir CLAUDE.md) + dernière commande
 * connue pour ce point. Même contenu que CommandBlock côté web
 * (apps/web/src/app/registre/[id]/page.tsx), jamais deux fois la logique.
 */
function CommandSection({
  points,
  relayPointId,
  controlMode,
  scheduledCommands,
  onSendCommand,
  sending,
  timeZone,
}: {
  points: { id: string; name: string; commands: PassportCommand[] }[];
  relayPointId: string;
  controlMode: "manual" | "automatic";
  scheduledCommands: ScheduledCommand[];
  onSendCommand: (pointId: string, requestedValue: number) => void;
  sending: boolean;
  timeZone: string | null;
}) {
  const point = points.find((candidate) => candidate.id === relayPointId);
  const lastCommand = point?.commands[0] ?? null;
  return (
    <View style={{ gap: 4 }}>
      <Text style={styles.strong}>{point?.name ?? relayPointId}</Text>
      <View style={styles.commandButtons}>
        <Button
          title={t("web.registre.command_turn_on")}
          onPress={() => onSendCommand(relayPointId, 1)}
          disabled={sending}
        />
        <Button
          title={t("web.registre.command_turn_off")}
          onPress={() => onSendCommand(relayPointId, 0)}
          disabled={sending}
        />
      </View>
      <Text style={{ ...styles.muted, fontWeight: "600" }}>
        {t("web.registre.command_last_title")}
      </Text>
      {lastCommand ? (
        <>
          <Text>
            {t(`command_status.${lastCommand.status}`)} —{" "}
            {t("web.registre.command_requested_value", {
              value: formatNumber(locale, lastCommand.requested_value),
            })}
            {lastCommand.actual_value !== null &&
              ` — ${t("web.registre.command_actual_value", {
                value: formatNumber(locale, lastCommand.actual_value),
              })}`}
          </Text>
          {lastCommand.failure_reason && (
            <Text>
              {t("web.registre.command_failure_reason", {
                reason: t(`command_failure_reason.${lastCommand.failure_reason}`),
              })}
            </Text>
          )}
          <Text style={styles.muted}>
            {t("web.registre.command_at", {
              when: formatDateTime(locale, lastCommand.created_at, timeZone),
            })}
          </Text>
        </>
      ) : (
        <Text style={styles.muted}>{t("web.registre.command_no_command")}</Text>
      )}

      {/* Lecture seule (parité web/mobile, audit de fermeture V2,
          07/10/2026) : planifier ou configurer l'automatisation reste un
          geste d'administration, web uniquement (ADR 014 §11) — un
          technicien a seulement besoin de voir ce qui est déjà programmé
          ou actif avant d'intervenir manuellement sur l'équipement. */}
      <Text style={{ ...styles.muted, fontWeight: "600", marginTop: 8 }}>
        {t("web.registre.control_mode_title")}
      </Text>
      <Text>
        {t(`control_mode.${controlMode}`)} — {t(`web.registre.control_mode_explanation.${controlMode}`)}
      </Text>

      {scheduledCommands.length > 0 && (
        <>
          <Text style={{ ...styles.muted, fontWeight: "600", marginTop: 8 }}>
            {t("web.registre.scheduled_command_list_title")}
          </Text>
          {scheduledCommands.map((scheduled) => (
            <Text key={scheduled.id} style={styles.muted}>
              {t(`scheduled_command_status.${scheduled.status}`)} —{" "}
              {t("web.registre.command_requested_value", {
                value: formatNumber(locale, scheduled.requested_value),
              })}{" "}
              {t("web.registre.scheduled_command_for", {
                when: formatDateTime(locale, scheduled.scheduled_for, timeZone),
              })}
            </Text>
          ))}
        </>
      )}
    </View>
  );
}

function StatusLine({ status, timeZone }: { status: EquipmentStatus; timeZone: string | null }) {
  const { key, params } = statusMessage(status);
  // Les paramètres sont eux-mêmes des clés (états) ou une date à mettre en forme.
  const rendered = Object.fromEntries(
    Object.entries(params ?? {}).map(([name, value]) => [
      name,
      name === "since" ? formatDateTime(locale, value, timeZone) : t(value),
    ]),
  );
  // Même vocabulaire d'état universel que le web (StatusBadge.tsx,
  // ADR 014) : jamais un deuxième jeu de couleurs pour la même signification.
  const assetStatus = equipmentStatusToAssetStatus(status);
  return (
    <View style={styles.statusLine}>
      <AssetStatusBadge status={assetStatus} label={t(`asset_status.${assetStatus}`)} />
      <Text>{t(key, rendered)}</Text>
    </View>
  );
}

function UnitView({ unit }: { unit: PassportUnit }) {
  return (
    <>
      <Text style={styles.strong}>
        {unit.manufacturer} {unit.reference}
      </Text>
      <Text>
        {t("mobile.passport.equipment_type", { type: t(`equipment_type.${unit.equipment_type}`) })}
      </Text>
      {unit.manufacturer_designation && (
        <Text style={styles.muted}>{unit.manufacturer_designation}</Text>
      )}
      <Text>{t("mobile.passport.serial", { serial: unit.serial_number })}</Text>
      {unit.asset_code && (
        <Text>{t("mobile.passport.asset_code", { code: unit.asset_code })}</Text>
      )}
      <Text>{t("mobile.passport.state", { state: t(`lifecycle.${unit.lifecycle_state}`) })}</Text>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    gap: 12,
  },
  label: {
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 6,
    padding: 10,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
  },
  error: {
    color: colors.danger,
  },
  workOrderLink: {
    color: colors.link,
    textDecorationLine: "underline",
  },
  scanner: {
    gap: 8,
  },
  commandButtons: {
    flexDirection: "row",
    gap: 12,
  },
  camera: {
    height: 280,
    borderRadius: 8,
    overflow: "hidden",
  },
  passport: {
    gap: 12,
    marginTop: 8,
  },
  section: {
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingTop: 8,
    gap: 4,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  strong: {
    fontWeight: "600",
  },
  muted: {
    color: colors.textMuted,
  },
  statusLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  signalRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    paddingVertical: 4,
  },
  signalText: {
    flex: 1,
    gap: 2,
  },
});
