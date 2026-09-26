import { useRef, useState } from "react";
import { type BarcodeScanningResult, CameraView, useCameraPermissions } from "expo-camera";
import {
  ActivityIndicator,
  Button,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { locale, t } from "../src/lib/i18n";
import { formatDate, formatDateTime, formatNumber } from "../src/i18n/translator";
import {
  type EquipmentStatus,
  type Passport,
  type PassportCommand,
  type PassportUnit,
  fetchPassportByTag,
  fetchSimulatedRelayPointId,
  isPlatformTag,
  parseTagCode,
  sendCommand,
  statusMessage,
} from "../src/lib/passport";

/**
 * Lecture de l'étiquette par l'appareil photo, ou saisie du code imprimé sous
 * le QR (même vérification dans les deux cas : `parseTagCode`). Le QR ne
 * contient qu'un code opaque ; tout le contenu vient du serveur, selon les
 * droits de la personne connectée.
 */
export default function PasseportScreen() {
  const auth = useAuth();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [passport, setPassport] = useState<Passport | null>(null);
  const [relayPointId, setRelayPointId] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  // Un QR reste devant l'objectif plusieurs images de suite : une seule lecture.
  const handled = useRef(false);
  // Retenu pour rafraîchir le passeport après l'envoi d'une commande, sans
  // demander à la personne de rescanner l'étiquette.
  const lastCode = useRef<string | null>(null);

  async function lookUp(raw: string) {
    setPassport(null);
    setRelayPointId(null);
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
    const result = await fetchPassportByTag(config.apiUrl, token, code, locale);
    if (result.ok) {
      lastCode.current = code;
      setPassport(result.passport);
      if (result.passport.node_type === "functional_location") {
        setRelayPointId(
          await fetchSimulatedRelayPointId(config.apiUrl, token, result.passport.node_id),
        );
      }
    } else {
      setMessage(t(result.messageKey, result.params));
    }
    setLoading(false);
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
    // Rejoue la lecture pour afficher l'état à jour de la commande.
    if (lastCode.current) {
      await lookUp(lastCode.current);
    } else {
      setLoading(false);
    }
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
      />
      <Button title={t("mobile.passport.show")} onPress={() => lookUp(input)} disabled={loading} />
      {loading && <ActivityIndicator />}
      {message && <Text style={styles.error}>{message}</Text>}
      {passport && (
        <PassportView
          passport={passport}
          relayPointId={relayPointId}
          onSendCommand={sendTestCommand}
          sending={loading}
        />
      )}
    </ScrollView>
  );
}

function PassportView({
  passport,
  relayPointId,
  onSendCommand,
  sending,
}: {
  passport: Passport;
  relayPointId: string | null;
  onSendCommand: (pointId: string, requestedValue: number) => void;
  sending: boolean;
}) {
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
      {passport.space_path && passport.space_path.length > 0 && (
        <Text style={styles.muted}>{passport.space_path.map((s) => s.name).join(" › ")}</Text>
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
            onSendCommand={onSendCommand}
            sending={sending}
            timeZone={timeZone}
          />
        </Section>
      )}

      <Section title={t("mobile.passport.signals")}>
        {alarms.map((alarm) => (
          <Text key={alarm.id}>
            {t("mobile.passport.alarm")} · {t(`severity.${alarm.severity}`)} ·{" "}
            {t(`condition_state.${alarm.condition_state}`)} · {t(`ack_state.${alarm.ack_state}`)}
            {"\n"}
            {alarm.message}
          </Text>
        ))}
        {passport.open_findings.map((finding) => (
          <Text key={finding.id}>
            {t("mobile.passport.finding")} · {t(`severity.${finding.severity}`)} ·{" "}
            {t(`certainty.${finding.certainty}`)} · {t(`condition_state.${finding.condition_state}`)}
            {"\n"}
            {finding.title}
          </Text>
        ))}
        {alarms.length === 0 && passport.open_findings.length === 0 && (
          <Text>{t("mobile.passport.nothing_open")}</Text>
        )}
      </Section>

      {passport.open_work_orders && passport.open_work_orders.length > 0 && (
        <Section title={t("mobile.passport.work_orders")}>
          {passport.open_work_orders.map((order) => (
            <Text key={order.id}>
              {order.title} ({t(`work_order.status.${order.status}`)})
            </Text>
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

      <Text style={styles.muted}>
        {timeZone
          ? t("mobile.passport.site_time", { timezone: timeZone })
          : t("mobile.passport.device_time")}
      </Text>
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
  onSendCommand,
  sending,
  timeZone,
}: {
  points: { id: string; name: string; commands: PassportCommand[] }[];
  relayPointId: string;
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
  return <Text style={status.current ? styles.strong : undefined}>{t(key, rendered)}</Text>;
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
    borderColor: "#ccc",
    borderRadius: 6,
    padding: 10,
  },
  error: {
    color: "#c0392b",
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
    borderTopColor: "#eee",
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
    color: "#666",
  },
});
