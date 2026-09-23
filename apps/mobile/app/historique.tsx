import { useEffect, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { locale, t } from "../src/lib/i18n";
import { formatDateTime } from "../src/i18n/translator";

type Intervention = {
  id: string;
  intervention_type: string;
  summary: string | null;
  started_at: string;
};

export default function HistoriqueScreen() {
  const auth = useAuth();
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auth.accessToken) return;
    auth.getAccessToken().then((token) => {
      if (!token) return;
      fetch(`${config.apiUrl}/interventions`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => {
          if (!res.ok) throw new Error(`${res.status}`);
          return res.json();
        })
        .then((data: Intervention[]) => setInterventions(data.reverse()))
        .catch(() => setError(t("mobile.history.load_failed")));
    });
  }, [auth.accessToken]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t("mobile.history.title")}</Text>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={interventions}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={<Text>{t("mobile.history.empty")}</Text>}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.rowType}>
              {t(`intervention_type.${item.intervention_type}`)} —{" "}
              {formatDateTime(locale, item.started_at)}
            </Text>
            {item.summary && <Text>{item.summary}</Text>}
          </View>
        )}
      />
    </View>
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
    color: "#c0392b",
    marginBottom: 12,
  },
  row: {
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
    paddingVertical: 10,
  },
  rowType: {
    fontWeight: "600",
  },
});
