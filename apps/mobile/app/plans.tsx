import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Linking, Pressable, StyleSheet, View } from "react-native";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { locale, t } from "../src/lib/i18n";
import { formatDateTime } from "../src/i18n/translator";
import { fetchPortfolioFloorPlans, type PortfolioFloorPlan } from "../src/lib/floorPlans";
import { colors } from "../src/design/colors";
import { Card } from "../src/design/Card";
import { Text } from "../src/design/Text";

/**
 * Plans/BIM, terrain, lecture seule (maquette de référence, 06/10/2026) :
 * consultation uniquement — ouvre le fichier déjà envoyé dans le lecteur du
 * téléphone (image ou PDF selon `contentType`). Poser ou déplacer un
 * équipement sur le plan reste réservé à l'éditeur web, qui a besoin d'un
 * grand écran et d'une souris pour un geste de précision (décision de
 * périmètre, pas un oubli).
 */
export default function PlansScreen() {
  const auth = useAuth();
  const [plans, setPlans] = useState<PortfolioFloorPlan[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth.accessToken) return;
    let cancelled = false;
    auth.getAccessToken().then(async (token) => {
      if (!token) return;
      try {
        const result = await fetchPortfolioFloorPlans(config.apiUrl, token);
        if (!cancelled) setPlans(result);
      } catch {
        if (!cancelled) setError(t("mobile.plans.load_failed"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [auth.accessToken]);

  async function openPlan(plan: PortfolioFloorPlan) {
    setOpenError(null);
    try {
      await Linking.openURL(plan.downloadUrl);
    } catch {
      setOpenError(t("mobile.plans.open_failed"));
    }
  }

  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      {openError && <Text style={styles.error}>{openError}</Text>}
      <FlatList
        data={plans}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={!error ? <Text style={styles.muted}>{t("mobile.plans.empty")}</Text> : null}
        renderItem={({ item }) => (
          <Pressable onPress={() => openPlan(item)} accessibilityRole="button">
            <Card style={styles.card}>
              <Text style={styles.strong}>
                {item.siteName} · {item.spaceCode} — {item.spaceName}
              </Text>
              <Text style={styles.muted}>{t("mobile.plans.version", { version: item.version })}</Text>
              <Text style={styles.muted}>
                {t("mobile.plans.uploaded_at", { date: formatDateTime(locale, item.uploadedAt) })}
              </Text>
              <Text style={styles.link}>{t("mobile.plans.open")}</Text>
            </Card>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: colors.background,
  },
  list: {
    gap: 10,
  },
  card: {
    gap: 4,
  },
  error: {
    color: colors.danger,
    marginBottom: 12,
  },
  muted: {
    color: colors.textMuted,
    fontSize: 13,
  },
  strong: {
    fontWeight: "600",
  },
  link: {
    color: colors.link,
    fontWeight: "600",
    marginTop: 4,
  },
});
