import { useCallback, useEffect, useRef, useState } from "react";
import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";

import { config } from "../../src/lib/config";
import { useAuth } from "../../src/lib/auth";
import { lastSyncedAt, listInterventionHistory, type CachedIntervention } from "../../src/lib/db";
import { locale, t } from "../../src/lib/i18n";
import { HISTORY_WINDOW_DAYS, synchronize } from "../../src/lib/sync";
import { formatDateTime } from "../../src/i18n/translator";
import { colors } from "../../src/design/colors";
import { Screen } from "../../src/design/Screen";
import { Text } from "../../src/design/Text";

/** Lignes lues par page dans la base locale : le défilement reste fluide quel que soit l'historique. */
const PAGE_SIZE = 30;

/**
 * Onglet Maintenance (maquette de référence, 06/10/2026) : historique des
 * interventions + accès direct à « Nouvelle intervention ».
 *
 * Depuis la consolidation V5 (21/10/2026), l'historique est lu dans la base
 * LOCALE du téléphone, page par page, et non plus téléchargé en entier à chaque
 * ouverture (35 Mo à 100 000 lignes). Conséquences : l'écran s'affiche
 * immédiatement, fonctionne hors ligne, et la mise à jour (tirer pour actualiser,
 * ou à l'ouverture) ne transfère que ce qui a changé (voir src/lib/syncFeed.ts).
 * Le texte dit toujours de quand date ce qui est affiché : hors ligne, on montre
 * le dernier état connu et sa date, jamais un état présenté comme actuel.
 */
export default function MaintenanceScreen() {
  const router = useRouter();
  const auth = useAuth();
  const [interventions, setInterventions] = useState<CachedIntervention[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [syncedAt, setSyncedAt] = useState<string | null>(null);
  const [incomplete, setIncomplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Sans cet état, la liste vide s'affichait avant même la lecture locale : un
  // technicien avec un historique réel voyait "Aucune intervention" le temps du
  // chargement (audit UX du 02/10/2026 — ne jamais affirmer plus que ce que le
  // système sait).
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const loadingMore = useRef(false);

  const loadFirstPage = useCallback(async () => {
    const page = await listInterventionHistory({ limit: PAGE_SIZE });
    setInterventions(page);
    setHasMore(page.length === PAGE_SIZE);
    setSyncedAt(await lastSyncedAt("interventions"));
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore.current || !hasMore || interventions.length === 0) return;
    loadingMore.current = true;
    try {
      const last = interventions[interventions.length - 1];
      const page = await listInterventionHistory({
        limit: PAGE_SIZE,
        before: { startedAt: last.started_at, id: last.id },
      });
      setInterventions((previous) => [...previous, ...page]);
      setHasMore(page.length === PAGE_SIZE);
    } finally {
      loadingMore.current = false;
    }
  }, [hasMore, interventions]);

  const refresh = useCallback(async () => {
    const token = await auth.getAccessToken();
    if (!token) return;
    try {
      const result = await synchronize(config.apiUrl, token);
      setIncomplete(result.incomplete === true);
      setError(null);
    } catch {
      setError(t("mobile.history.load_failed"));
    }
    await loadFirstPage();
  }, [auth, loadFirstPage]);

  useEffect(() => {
    // D'abord ce que le téléphone connaît déjà (immédiat, même sans réseau), puis la mise à jour.
    loadFirstPage()
      .catch(() => setError(t("mobile.history.load_failed")))
      .finally(() => setLoading(false));
    if (auth.accessToken) {
      refresh();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule fois par session ouverte.
  }, [auth.accessToken]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

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
        <Text style={styles.muted}>
          {syncedAt
            ? t("mobile.history.last_sync", { date: formatDateTime(locale, syncedAt) })
            : t("mobile.history.never_synced")}
        </Text>
        {incomplete && <Text style={styles.muted}>{t("mobile.history.sync_incomplete")}</Text>}
        {error && <Text style={styles.error}>{error}</Text>}
        {loading ? (
          <ActivityIndicator />
        ) : (
          <FlatList
            data={interventions}
            keyExtractor={(item) => item.id}
            onEndReached={loadMore}
            onEndReachedThreshold={0.5}
            refreshing={refreshing}
            onRefresh={onRefresh}
            ListEmptyComponent={<Text style={styles.muted}>{t("mobile.history.empty")}</Text>}
            ListFooterComponent={
              <Text style={styles.muted}>
                {t("mobile.history.window_note", { days: HISTORY_WINDOW_DAYS })}
              </Text>
            }
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
