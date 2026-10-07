import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { t } from "../lib/i18n";
import { colors } from "./colors";

/**
 * Barre compacte (maquette de référence, 06/10/2026) : jamais de sidebar
 * permanente sur mobile — ce bandeau ouvre le tiroir de navigation
 * superposé (voir Drawer.tsx). `alertCount` vient toujours d'une donnée
 * réelle déjà chargée par l'écran appelant, jamais calculé ici.
 */
export function TopBar({
  onOpenDrawer,
  alertCount,
}: {
  onOpenDrawer: () => void;
  alertCount?: number | null;
}) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.bar, { paddingTop: insets.top + 8 }]}>
      <Pressable
        onPress={onOpenDrawer}
        style={styles.iconButton}
        accessibilityRole="button"
        accessibilityLabel={t("mobile.nav.open_menu")}
      >
        <Ionicons name="menu" size={24} color={colors.textPrimary} />
      </Pressable>
      <Text style={styles.brand}>{t("common.app_name")}</Text>
      <View style={styles.actions}>
        <Pressable
          onPress={() => router.push("/alertes")}
          style={styles.iconButton}
          accessibilityRole="button"
          accessibilityLabel={t("mobile.alerts.title")}
        >
          <Ionicons name="notifications-outline" size={22} color={colors.textPrimary} />
          {!!alertCount && alertCount > 0 && (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{alertCount > 99 ? "99+" : alertCount}</Text>
            </View>
          )}
        </Pressable>
        <Pressable
          onPress={() => router.push("/profil")}
          style={styles.iconButton}
          accessibilityRole="button"
          accessibilityLabel={t("mobile.profile.title")}
        >
          <Ionicons name="person-circle-outline" size={24} color={colors.textPrimary} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: 12,
    paddingBottom: 8,
  },
  brand: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "700",
  },
  actions: {
    flexDirection: "row",
    gap: 4,
  },
  iconButton: {
    minWidth: 44,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  badge: {
    position: "absolute",
    top: 4,
    right: 4,
    backgroundColor: colors.danger,
    borderRadius: 9,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 3,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: {
    color: colors.background,
    fontSize: 10,
    fontWeight: "700",
  },
});
