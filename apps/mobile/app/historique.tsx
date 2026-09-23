import { useEffect, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";

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
        .catch((err: Error) => setError(err.message));
    });
  }, [auth.accessToken]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Historique (envoyées au serveur)</Text>
      {error && <Text style={styles.error}>Erreur : {error}</Text>}
      <FlatList
        data={interventions}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={<Text>Aucune intervention envoyée pour l'instant.</Text>}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.rowType}>
              {item.intervention_type === "ronde" ? "Ronde" : "Intervention"} —{" "}
              {new Date(item.started_at).toLocaleString()}
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
