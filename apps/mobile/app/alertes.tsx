import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { locale, t } from "../src/lib/i18n";
import { formatDateTime } from "../src/i18n/translator";
import { type Alert, fetchOpenAlerts } from "../src/lib/alerts";
import { colors } from "../src/design/colors";
import { SeverityBadge } from "../src/design/StatusBadge";

/**
 * Portefeuille terrain des alarmes et constats ouverts (même source et même
 * tri que la page web /alarmes) : un technicien peut consulter ce qui est
 * ouvert sur son périmètre sans avoir d'abord scanné une étiquette — geste
 * manquant identifié à l'audit mobile du 02/10/2026 (chantier UX/UI,
 * directive de Mohamed).
 */
export default function AlertesScreen() {
  const auth = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth.accessToken) return;
    let cancelled = false;
    auth.getAccessToken().then(async (token) => {
      if (!token) return;
      try {
        const result = await fetchOpenAlerts(config.apiUrl, token);
        if (!cancelled) setAlerts(result);
      } catch {
        if (!cancelled) setError(t("mobile.alerts.load_failed"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [auth.accessToken]);

  if (loading) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>{t("mobile.alerts.title")}</Text>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t("mobile.alerts.title")}</Text>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={alerts}
        keyExtractor={(item) => `${item.kind}-${item.id}`}
        ListEmptyComponent={<Text>{t("mobile.alerts.empty")}</Text>}
        renderItem={({ item }) => <AlertRow alert={item} />}
      />
    </View>
  );
}

function AlertRow({ alert }: { alert: Alert }) {
  const router = useRouter();
  const content = (
    <>
      <SeverityBadge severity={alert.severity} label={t(`severity.${alert.severity}`)} />
      <View style={styles.rowText}>
        <Text style={styles.strong}>
          {t(`mobile.alerts.kind_${alert.kind}`)}
          {alert.equipmentCode && alert.equipmentName
            ? ` · ${alert.equipmentCode} — ${alert.equipmentName}`
            : ""}
        </Text>
        <Text>{alert.message}</Text>
        <Text style={styles.muted}>
          {t(`ack_state.${alert.ackState}`)} · {formatDateTime(locale, alert.raisedAt)}
        </Text>
      </View>
    </>
  );
  if (!alert.equipmentId) {
    return <View style={styles.row}>{content}</View>;
  }
  return (
    <Pressable
      style={styles.row}
      onPress={() =>
        router.push({ pathname: "/passeport", params: { functionalLocationId: alert.equipmentId! } })
      }
    >
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
  },
  title: {
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 16,
  },
  error: {
    color: colors.danger,
    marginBottom: 12,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
    paddingVertical: 10,
  },
  rowText: {
    flex: 1,
    gap: 2,
  },
  strong: {
    fontWeight: "600",
  },
  muted: {
    color: colors.textMuted,
  },
});
