import { useState } from "react";
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
  type Passport,
  type PassportUnit,
  fetchPassportByTag,
  parseTagCode,
} from "../src/lib/passport";

// Saisie manuelle du code imprimé sous le QR. La lecture par la caméra
// viendra ensuite : elle remplira ce même champ.
export default function PasseportScreen() {
  const auth = useAuth();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [passport, setPassport] = useState<Passport | null>(null);

  async function lookUp() {
    setPassport(null);
    const code = parseTagCode(input);
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
    setLoading(false);
    if (result.ok) {
      setPassport(result.passport);
    } else {
      setMessage(t(result.messageKey, result.params));
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.label}>{t("mobile.passport.tag_code")}</Text>
      <TextInput
        style={styles.input}
        value={input}
        onChangeText={setInput}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder={t("mobile.passport.tag_placeholder")}
      />
      <Button title={t("mobile.passport.show")} onPress={lookUp} disabled={loading} />
      {loading && <ActivityIndicator />}
      {message && <Text style={styles.error}>{message}</Text>}
      {passport && <PassportView passport={passport} />}
    </ScrollView>
  );
}

function PassportView({ passport }: { passport: Passport }) {
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
