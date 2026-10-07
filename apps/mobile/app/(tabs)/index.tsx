import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Button, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import NetInfo from "@react-native-community/netinfo";

import { config } from "../../src/lib/config";
import { t, locale } from "../../src/lib/i18n";
import { formatDateTime } from "../../src/i18n/translator";
import { useAuth } from "../../src/lib/auth";
import { countPendingInterventions } from "../../src/lib/db";
import { type ActivityItem, type DashboardCounts, fetchDashboardCounts, fetchRecentActivity } from "../../src/lib/dashboard";
import { synchronize } from "../../src/lib/sync";
import { colors } from "../../src/design/colors";
import { KpiTile, QuickAction } from "../../src/design/Card";
import { Screen } from "../../src/design/Screen";
import { Text } from "../../src/design/Text";

/**
 * Accueil = tableau de bord réel (maquette de référence, 06/10/2026) :
 * uniquement des comptes et une activité déjà exposés par l'API (voir
 * src/lib/dashboard.ts) — jamais un chiffre ou une ligne fabriquée pour
 * remplir l'écran. Remplace l'ancien accueil (liste de boutons) sans rien
 * retirer : chaque bouton devient soit un onglet, soit une action rapide,
 * soit une entrée du tiroir.
 */
export default function HomeScreen() {
  const router = useRouter();
  const auth = useAuth();
  const [counts, setCounts] = useState<DashboardCounts | null>(null);
  const [countsError, setCountsError] = useState<string | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const loadDashboard = useCallback(async () => {
    const token = await auth.getAccessToken();
    if (!token) return;
    setCountsError(null);
    setActivityError(null);
    const [countsResult, activityResult] = await Promise.allSettled([
      fetchDashboardCounts(config.apiUrl, token),
      fetchRecentActivity(config.apiUrl, token),
    ]);
    if (countsResult.status === "fulfilled") {
      setCounts(countsResult.value);
    } else {
      setCountsError(t("mobile.home.counts_load_failed"));
    }
    if (activityResult.status === "fulfilled") {
      setActivity(activityResult.value);
    } else {
      setActivityError(t("mobile.home.activity_load_failed"));
    }
  }, [auth]);

  useEffect(() => {
    if (!auth.accessToken) {
      setCounts(null);
      setActivity([]);
      return;
    }
    setDashboardLoading(true);
    loadDashboard().finally(() => setDashboardLoading(false));
  }, [auth.accessToken, loadDashboard]);

  async function refreshPendingCount() {
    setPendingCount(await countPendingInterventions());
  }

  async function runSync() {
    const token = await auth.getAccessToken();
    if (!token) return;
    await synchronize(config.apiUrl, token);
    await refreshPendingCount();
  }

  // Synchronise dès que le réseau revient, sans attendre une action du
  // technicien : c'est tout l'intérêt du mode hors ligne (voir ADR 010).
  useEffect(() => {
    refreshPendingCount();
    const unsubscribe = NetInfo.addEventListener((state) => {
      if (state.isConnected) {
        runSync();
      }
    });
    return unsubscribe;
  }, [auth.accessToken]);

  useFocusEffect(
    useCallback(() => {
      refreshPendingCount();
    }, []),
  );

  async function onRefresh() {
    setRefreshing(true);
    await Promise.all([loadDashboard(), refreshPendingCount()]);
    setRefreshing(false);
  }

  if (auth.isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!auth.accessToken) {
    return (
      <View style={styles.centered}>
        <Text style={styles.title}>{t("common.app_name")}</Text>
        <Text style={styles.subtitle}>{t("mobile.home.subtitle")}</Text>
        <Button title={t("common.sign_in")} onPress={auth.signIn} disabled={!auth.canSignIn} />
        {auth.error && <Text style={styles.error}>{t(auth.error)}</Text>}
      </View>
    );
  }

  return (
    <Screen alertCount={counts?.openAlerts}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {dashboardLoading ? (
          <ActivityIndicator />
        ) : (
          <>
            {countsError && <Text style={styles.error}>{countsError}</Text>}
            <View style={styles.kpiGrid}>
              <KpiTile label={t("mobile.home.kpi_sites")} value={counts?.sites ?? null} />
              <KpiTile label={t("mobile.home.kpi_buildings")} value={counts?.buildings ?? null} />
              <KpiTile label={t("mobile.home.kpi_equipment")} value={counts?.equipment ?? null} />
              <KpiTile
                label={t("mobile.home.kpi_alerts")}
                value={counts?.openAlerts ?? null}
                onPress={() => router.push("/alertes")}
              />
            </View>

            <Text style={styles.sectionTitle}>{t("mobile.home.quick_actions_title")}</Text>
            <View style={styles.quickActions}>
              <QuickAction
                label={t("mobile.home.new_intervention")}
                icon={<IconPlaceholder symbol="+" />}
                onPress={() => router.push("/nouvelle-intervention")}
              />
              <QuickAction
                label={t("mobile.alerts.title")}
                icon={<IconPlaceholder symbol="!" />}
                onPress={() => router.push("/alertes")}
              />
              <QuickAction
                label={t("mobile.energy.title")}
                icon={<IconPlaceholder symbol="E" />}
                onPress={() => router.push("/energie")}
              />
              <QuickAction
                label={t("mobile.nav.add_site")}
                icon={<IconPlaceholder symbol="S" />}
                onPress={() => router.push("/ajouter-site")}
              />
            </View>

            {pendingCount > 0 && (
              <View style={styles.pendingRow}>
                <Text>{t("mobile.home.pending", { count: pendingCount })}</Text>
                <Button title={t("mobile.home.sync")} onPress={runSync} />
              </View>
            )}

            <Text style={styles.sectionTitle}>{t("mobile.home.activity_title")}</Text>
            {activityError && <Text style={styles.error}>{activityError}</Text>}
            {activity.length === 0 && !activityError ? (
              <Text style={styles.muted}>{t("mobile.home.activity_empty")}</Text>
            ) : (
              activity.map((item) => (
                <View key={item.key} style={styles.activityRow}>
                  <Text style={styles.strong}>
                    {t(`timeline.kind_${item.kind}`)}
                    {item.equipmentLabel ? ` · ${item.equipmentLabel}` : ""}
                  </Text>
                  {item.title && <Text>{item.title}</Text>}
                  <Text style={styles.muted}>{formatDateTime(locale, item.at)}</Text>
                </View>
              ))
            )}
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

// Espace réservé en attendant une icône dédiée par action (ADR 013 :
// jamais la couleur seule pour porter le sens, mais un glyphe simple suffit
// ici — pas de bibliothèque d'icônes supplémentaire pour 4 pastilles).
function IconPlaceholder({ symbol }: { symbol: string }) {
  return <Text style={styles.iconPlaceholder}>{symbol}</Text>;
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    padding: 24,
    backgroundColor: colors.background,
  },
  container: {
    padding: 16,
    gap: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: "600",
  },
  subtitle: {
    color: colors.textMuted,
  },
  error: {
    color: colors.danger,
  },
  kpiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    marginTop: 4,
  },
  quickActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  iconPlaceholder: {
    color: colors.accent,
    fontSize: 20,
    fontWeight: "700",
  },
  pendingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  activityRow: {
    gap: 2,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
    paddingVertical: 8,
  },
  strong: {
    fontWeight: "600",
  },
  muted: {
    color: colors.textMuted,
  },
});
