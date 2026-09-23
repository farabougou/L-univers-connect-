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
import {
  type Passport,
  type PassportUnit,
  fetchPassportByTag,
  lifecycleLabel,
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
      setMessage("Code d'étiquette invalide.");
      return;
    }
    const token = await auth.getAccessToken();
    if (!token) {
      setMessage("Connectez-vous d'abord.");
      return;
    }
    setLoading(true);
    setMessage(null);
    const result = await fetchPassportByTag(config.apiUrl, token, code);
    setLoading(false);
    if (result.ok) {
      setPassport(result.passport);
    } else {
      setMessage(result.message);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.label}>Code de l'étiquette</Text>
      <TextInput
        style={styles.input}
        value={input}
        onChangeText={setInput}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="Code imprimé sous le QR"
      />
      <Button title="Afficher le passeport" onPress={lookUp} disabled={loading} />
      {loading && <ActivityIndicator />}
      {message && <Text style={styles.error}>{message}</Text>}
      {passport && <PassportView passport={passport} />}
    </ScrollView>
  );
}

function PassportView({ passport }: { passport: Passport }) {
  const unit = passport.physical_unit ?? passport.current_unit ?? null;
  return (
    <View style={styles.passport}>
      {passport.functional_location && (
        <Section title="Position">
          <Text style={styles.strong}>
            {passport.functional_location.code} — {passport.functional_location.name}
          </Text>
        </Section>
      )}
      {passport.space_path && passport.space_path.length > 0 && (
        <Text style={styles.muted}>{passport.space_path.map((s) => s.name).join(" › ")}</Text>
      )}

      <Section title="Équipement">
        {unit ? <UnitView unit={unit} /> : <Text>Aucun exemplaire en place.</Text>}
      </Section>

      {passport.points && passport.points.length > 0 && (
        <Section title="Dernières mesures">
          {passport.points.map((point) => (
            <Text key={point.id}>
              {point.name} :{" "}
              {point.latest
                ? `${point.latest.value} ${point.unit} (${new Date(
                    point.latest.measured_at,
                  ).toLocaleString()})`
                : "aucune mesure"}
              {point.latest && point.latest.quality_flags.length > 0 ? " ⚠️" : ""}
            </Text>
          ))}
        </Section>
      )}

      <Section title="Alarmes et constats ouverts">
        {(passport.open_alarms ?? []).map((alarm) => (
          <Text key={alarm.id}>
            🔔 [{alarm.severity}] {alarm.message}
          </Text>
        ))}
        {passport.open_findings.map((finding) => (
          <Text key={finding.id}>
            🔎 [{finding.severity}] {finding.title}
          </Text>
        ))}
        {(passport.open_alarms ?? []).length === 0 && passport.open_findings.length === 0 && (
          <Text>Rien d'ouvert.</Text>
        )}
      </Section>

      {passport.open_work_orders && passport.open_work_orders.length > 0 && (
        <Section title="Ordres de travail en cours">
          {passport.open_work_orders.map((order) => (
            <Text key={order.id}>• {order.title}</Text>
          ))}
        </Section>
      )}

      {passport.recent_interventions && passport.recent_interventions.length > 0 && (
        <Section title="Dernières interventions">
          {passport.recent_interventions.map((item) => (
            <Text key={item.id}>
              {new Date(item.started_at).toLocaleDateString()} —{" "}
              {item.action_label ?? item.summary ?? "sans résumé"}
              {item.symptom_label ? ` (${item.symptom_label})` : ""}
            </Text>
          ))}
        </Section>
      )}
    </View>
  );
}

function UnitView({ unit }: { unit: PassportUnit }) {
  return (
    <>
      <Text style={styles.strong}>
        {unit.manufacturer} {unit.reference}
      </Text>
      <Text>N° de série : {unit.serial_number}</Text>
      <Text>État : {lifecycleLabel(unit.lifecycle_state)}</Text>
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
