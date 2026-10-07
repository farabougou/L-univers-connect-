import { useEffect, useRef, useState } from "react";
import { Ionicons } from "@expo/vector-icons";
import { Animated, Dimensions, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "../lib/auth";
import { config } from "../lib/config";
import { t } from "../lib/i18n";
import { fetchMe } from "../lib/me";
import { canManage } from "../lib/roles";
import { colors } from "./colors";

const DRAWER_WIDTH = Math.min(300, Dimensions.get("window").width * 0.82);

type DrawerItem = {
  key: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  route: string;
};

// Uniquement des écrans réellement implémentés (CLAUDE.md : jamais une
// navigation qui ne mène nulle part). "Supervision"/"Rapports"/
// "Administration" de la maquette ne sont pas dans la liste tant qu'ils
// n'existent pas (ADR 013) — DEFER documenté dans la matrice.
const BASE_ITEMS: DrawerItem[] = [
  { key: "home", label: "mobile.nav.home", icon: "home-outline", route: "/" },
  { key: "assets", label: "mobile.assets.title", icon: "cube-outline", route: "/actifs" },
  { key: "alerts", label: "mobile.alerts.title", icon: "warning-outline", route: "/alertes" },
  { key: "maintenance", label: "mobile.nav.maintenance", icon: "build-outline", route: "/maintenance" },
  { key: "energy", label: "mobile.energy.title", icon: "flash-outline", route: "/energie" },
  { key: "plans", label: "mobile.plans.title", icon: "map-outline", route: "/plans" },
  { key: "profile", label: "mobile.profile.title", icon: "person-circle-outline", route: "/profil" },
];

// N'apparaît que pour les rôles qui peuvent réellement créer un site
// (mêmes rôles que le serveur, voir src/lib/roles.ts) : jamais un formulaire
// ouvert pour échouer ensuite sur un 403.
const ADD_SITE_ITEM: DrawerItem = {
  key: "add_site",
  label: "mobile.nav.add_site",
  icon: "add-circle-outline",
  route: "/ajouter-site",
};

/**
 * Menu tiroir en superposition (maquette de référence, 06/10/2026) :
 * jamais une sidebar permanente sur mobile — un `Modal` + `Animated` qui
 * glisse par-dessus le contenu et se referme au tap sur le fond, pas une
 * disposition imbriquée de navigateur (choix volontaire : ce bac à sable ne
 * peut pas exécuter l'application sur un appareil réel pour valider une
 * mécanique de navigation plus complexe).
 */
export function AppDrawer({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const router = useRouter();
  const auth = useAuth();
  const insets = useSafeAreaInsets();
  const translateX = useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const [canAddSite, setCanAddSite] = useState(false);

  useEffect(() => {
    Animated.timing(translateX, {
      toValue: visible ? 0 : -DRAWER_WIDTH,
      duration: 220,
      useNativeDriver: true,
    }).start();
  }, [visible, translateX]);

  useEffect(() => {
    if (!visible || !auth.accessToken) return;
    auth.getAccessToken().then(async (token) => {
      if (!token) return;
      const me = await fetchMe(config.apiUrl, token);
      setCanAddSite(me ? canManage(me.roles) : false);
    });
  }, [visible, auth.accessToken]);

  const items = canAddSite ? [...BASE_ITEMS, ADD_SITE_ITEM] : BASE_ITEMS;

  function navigate(route: string) {
    onClose();
    router.push(route as never);
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose} accessibilityRole="button" accessibilityLabel={t("mobile.nav.close_menu")}>
        <Animated.View
          style={[
            styles.panel,
            { width: DRAWER_WIDTH, paddingTop: insets.top + 16, transform: [{ translateX }] },
          ]}
        >
          <Pressable onPress={(e) => e.stopPropagation()} style={styles.panelContent}>
            <Text style={styles.brand}>{t("common.app_name")}</Text>
            <View style={styles.items}>
              {items.map((item) => (
                <Pressable
                  key={item.key}
                  onPress={() => navigate(item.route)}
                  style={styles.item}
                  accessibilityRole="button"
                >
                  <Ionicons name={item.icon} size={20} color={colors.textPrimary} />
                  <Text style={styles.itemLabel}>{t(item.label)}</Text>
                </Pressable>
              ))}
            </View>
            <Pressable
              onPress={() => {
                onClose();
                auth.signOut();
              }}
              style={styles.item}
              accessibilityRole="button"
            >
              <Ionicons name="log-out-outline" size={20} color={colors.danger} />
              <Text style={[styles.itemLabel, { color: colors.danger }]}>{t("common.sign_out")}</Text>
            </Pressable>
          </Pressable>
        </Animated.View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: colors.overlay,
  },
  panel: {
    height: "100%",
    backgroundColor: colors.surface,
    borderRightWidth: 1,
    borderRightColor: colors.border,
  },
  panelContent: {
    flex: 1,
    paddingHorizontal: 16,
  },
  brand: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 24,
  },
  items: {
    flex: 1,
    gap: 4,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingVertical: 14,
    minHeight: 44,
  },
  itemLabel: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "500",
  },
});
