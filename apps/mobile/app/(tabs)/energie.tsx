import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, View } from "react-native";

import { config } from "../../src/lib/config";
import { useAuth } from "../../src/lib/auth";
import { locale, t } from "../../src/lib/i18n";
import { formatDate, formatNumber } from "../../src/i18n/translator";
import { type EnergyMeter, fetchEnergyPortfolio } from "../../src/lib/energy";
import { colors } from "../../src/design/colors";
import { Screen } from "../../src/design/Screen";
import { Text } from "../../src/design/Text";

/**
 * Portefeuille énergie, terrain (app/actifs.tsx et app/alertes.tsx en sont
 * les pendants Actifs/Alertes) — même source que le bloc « Énergie » du
 * Global Command Center web. Consommation brute par compteur uniquement :
 * jamais d'économies ni de ROI fabriqués pour cet écran.
 */
export default function EnergieScreen() {
  const auth = useAuth();
  const [meters, setMeters] = useState<EnergyMeter[]>([]);
  const [referenceDate, setReferenceDate] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth.accessToken) return;
    let cancelled = false;
    auth.getAccessToken().then(async (token) => {
      if (!token) return;
      try {
        const result = await fetchEnergyPortfolio(config.apiUrl, token);
        if (!cancelled) {
          setMeters(result.meters);
          setReferenceDate(result.referenceDate);
        }
      } catch {
        if (!cancelled) setError(t("mobile.energy.load_failed"));
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
      <Screen>
        <View style={styles.container}>
          <Text style={styles.title}>{t("mobile.energy.title")}</Text>
          <ActivityIndicator />
        </View>
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={styles.container}>
        <Text style={styles.title}>{t("mobile.energy.title")}</Text>
        {referenceDate && (
          <Text style={styles.muted}>
            {t("mobile.energy.reference_date", { date: formatDate(locale, referenceDate, null) })}
          </Text>
        )}
        {error && <Text style={styles.error}>{error}</Text>}
        <FlatList
          data={meters}
          keyExtractor={(item) => item.pointId}
          ListEmptyComponent={<Text style={styles.muted}>{t("mobile.energy.empty")}</Text>}
          renderItem={({ item }) => <MeterRow meter={item} />}
        />
      </View>
    </Screen>
  );
}

function MeterRow({ meter }: { meter: EnergyMeter }) {
  return (
    <View style={styles.row}>
      <Text style={styles.strong}>
        {meter.equipmentCode} {meter.equipmentName ? `— ${meter.equipmentName}` : ""}
      </Text>
      <Text>
        {meter.consumption !== null
          ? t("mobile.energy.consumption", {
              value: formatNumber(locale, meter.consumption),
              unit: meter.unit,
            })
          : t("mobile.energy.no_data")}
      </Text>
      {meter.previousConsumption !== null && (
        <Text style={styles.muted}>
          {t("mobile.energy.previous_consumption", {
            value: formatNumber(locale, meter.previousConsumption),
            unit: meter.unit,
          })}
        </Text>
      )}
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
    marginBottom: 4,
  },
  error: {
    color: colors.danger,
    marginBottom: 12,
  },
  row: {
    gap: 2,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
    paddingVertical: 10,
  },
  strong: {
    fontWeight: "600",
  },
  muted: {
    color: colors.textMuted,
    marginBottom: 8,
  },
});
