import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, TextInput, View } from "react-native";
import { useRouter } from "expo-router";

import { config } from "../../src/lib/config";
import { useAuth } from "../../src/lib/auth";
import { t } from "../../src/lib/i18n";
import { type AssetListItem, type Site, fetchAssets } from "../../src/lib/assets";
import { ASSET_STATUS_COLOR, type AssetStatus, colors } from "../../src/design/colors";
import { Screen } from "../../src/design/Screen";
import { AssetStatusBadge } from "../../src/design/StatusBadge";
import { Text } from "../../src/design/Text";

const ASSET_STATUSES: AssetStatus[] = Object.keys(ASSET_STATUS_COLOR) as AssetStatus[];

/**
 * Registre d'actifs filtrable, terrain (app/alertes.tsx en est le pendant
 * pour les alarmes/constats) — même source que le Global Command Center
 * web. Aucun écran mobile n'existait jusqu'ici pour parcourir le
 * portefeuille d'équipements autrement qu'en scannant une étiquette.
 */
export default function ActifsScreen() {
  const auth = useAuth();
  const router = useRouter();
  const [sites, setSites] = useState<Site[]>([]);
  const [assets, setAssets] = useState<AssetListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [siteFilter, setSiteFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<AssetStatus | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!auth.accessToken) return;
    let cancelled = false;
    auth.getAccessToken().then(async (token) => {
      if (!token) return;
      try {
        const result = await fetchAssets(config.apiUrl, token);
        if (!cancelled) {
          setSites(result.sites);
          setAssets(result.assets);
        }
      } catch {
        if (!cancelled) setError(t("mobile.assets.load_failed"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [auth.accessToken]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return assets.filter((asset) => {
      if (siteFilter && asset.siteId !== siteFilter) return false;
      if (statusFilter && asset.status !== statusFilter) return false;
      if (needle && !`${asset.code} ${asset.name}`.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [assets, siteFilter, statusFilter, query]);

  if (loading) {
    return (
      <Screen>
        <View style={styles.container}>
          <Text style={styles.title}>{t("mobile.assets.title")}</Text>
          <ActivityIndicator />
        </View>
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={styles.container}>
      <Text style={styles.title}>{t("mobile.assets.title")}</Text>
      {error && <Text style={styles.error}>{error}</Text>}
      <TextInput
        style={styles.search}
        value={query}
        onChangeText={setQuery}
        placeholder={t("mobile.assets.search_placeholder")}
        placeholderTextColor={colors.textMuted}
        autoCapitalize="none"
        autoCorrect={false}
      />
      <View style={styles.chipRow}>
        <Chip
          label={t("mobile.assets.filter_all_sites")}
          active={siteFilter === null}
          onPress={() => setSiteFilter(null)}
        />
        {sites.map((site) => (
          <Chip
            key={site.id}
            label={site.name}
            active={siteFilter === site.id}
            onPress={() => setSiteFilter(site.id === siteFilter ? null : site.id)}
          />
        ))}
      </View>
      <View style={styles.chipRow}>
        <Chip
          label={t("mobile.assets.filter_all_status")}
          active={statusFilter === null}
          onPress={() => setStatusFilter(null)}
        />
        {ASSET_STATUSES.map((status) => (
          <Chip
            key={status}
            label={t(`asset_status.${status}`)}
            active={statusFilter === status}
            onPress={() => setStatusFilter(status === statusFilter ? null : status)}
          />
        ))}
      </View>
      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={<Text style={styles.muted}>{t("mobile.assets.empty")}</Text>}
        renderItem={({ item }) => (
          <Pressable
            style={styles.row}
            onPress={() =>
              router.push({ pathname: "/passeport", params: { functionalLocationId: item.id } })
            }
          >
            <AssetStatusBadge status={item.status} label={t(`asset_status.${item.status}`)} />
            <View style={styles.rowText}>
              <Text style={styles.strong}>
                {item.code} — {item.name}
              </Text>
              {item.siteName && <Text style={styles.muted}>{item.siteName}</Text>}
            </View>
          </Pressable>
        )}
      />
      </View>
    </Screen>
  );
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, active ? styles.chipActive : undefined]}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
    >
      <Text style={active ? styles.chipTextActive : styles.chipText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    gap: 8,
  },
  title: {
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 8,
  },
  error: {
    color: colors.danger,
  },
  search: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginBottom: 4,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  chipActive: {
    borderColor: colors.selectedBorder,
    backgroundColor: colors.selectedBackground,
  },
  chipText: {
    color: colors.textMuted,
    fontSize: 13,
  },
  chipTextActive: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "600",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
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
