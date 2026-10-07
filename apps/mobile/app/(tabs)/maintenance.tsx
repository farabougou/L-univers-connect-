import { useEffect, useState } from "react";
import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";

import { config } from "../../src/lib/config";
import { useAuth } from "../../src/lib/auth";
import { locale, t } from "../../src/lib/i18n";
import { formatDateTime } from "../../src/i18n/translator";
import { colors } from "../../src/design/colors";
import { Screen } from "../../src/design/Screen";
import { Text } from "../../src/design/Text";

type Intervention = {
  id: string;
  intervention_type: string;
  summary: string | null;
  started_at: string;
};

/**
 * Onglet Maintenance (maquette de référence, 06/10/2026) : reprend l'écran
 * Historique existant (app/historique.tsx) et y ajoute l'accès direct à
 * « Nouvelle intervention », jusqu'ici uniquement accessible depuis
 * l'accueil — un technicien n'a plus besoin de revenir à l'accueil pour
 * créer une intervention.
 */
export default function MaintenanceScreen() {
  const router = useRouter();
  const auth = useAuth();
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Sans cet état, la liste vide s'affichait avant même la réponse du
  // serveur : un technicien avec un historique réel voyait "Aucune
  // intervention" le temps du chargement (trouvé par l'audit UX du
  // 02/10/2026 — ne jamais affirmer plus que ce que le système sait).
  const [loading, setLoading] = useState(true);

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
        .catch(() => setError(t("mobile.history.load_failed")))
        .finally(() => setLoading(false));
    });
  }, [auth.accessToken]);

  return (
    <Screen>
      <View style={styles.container}>
        <Text style={styles.title}>{t("mobile.history.title")}</Text>
        <Pressable
          style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
          onPress={() => router.push("/nouvelle-intervention")}
          accessibilityRole="button"
        >
          <Ionicons name="add-circle-outline" size={20} color={colors.background} />
          <Text style={styles.ctaLabel}>{t("mobile.home.new_intervention")}</Text>
        </Pressable>
        {error && <Text style={styles.error}>{error}</Text>}
        {loading ? (
          <ActivityIndicator />
        ) : (
          <FlatList
            data={interventions}
            keyExtractor={(item) => item.id}
            ListEmptyComponent={<Text style={styles.muted}>{t("mobile.history.empty")}</Text>}
            renderItem={({ item }) => (
              <View style={styles.row}>
                <Text style={styles.rowType}>
                  {t(`intervention_type.${item.intervention_type}`)} —{" "}
                  {formatDateTime(locale, item.started_at)}
                </Text>
                {item.summary && <Text style={styles.muted}>{item.summary}</Text>}
              </View>
            )}
          />
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    gap: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
  },
  cta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: colors.accent,
    borderRadius: 14,
    paddingVertical: 14,
    minHeight: 48,
  },
  ctaPressed: {
    opacity: 0.85,
  },
  ctaLabel: {
    color: colors.background,
    fontWeight: "700",
    fontSize: 15,
  },
  error: {
    color: colors.danger,
  },
  row: {
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
    paddingVertical: 10,
  },
  rowType: {
    fontWeight: "600",
  },
  muted: {
    color: colors.textMuted,
  },
});
