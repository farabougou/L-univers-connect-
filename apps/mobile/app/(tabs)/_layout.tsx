import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router/tabs";

import { colors } from "../../src/design/colors";
import { t } from "../../src/lib/i18n";

/**
 * Navigation inférieure limitée aux fonctions principales (maquette de
 * référence, 06/10/2026) : Accueil, Actifs, Maintenance, Énergie. Alertes,
 * Passeport, Ajouter un site et Profil restent accessibles depuis la barre
 * compacte ou le tiroir (voir src/design/Screen.tsx, Drawer.tsx) — jamais
 * dupliqués ici, pour ne pas surcharger la barre.
 */
export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.inactive,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t("mobile.nav.home"),
          tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="actifs"
        options={{
          title: t("mobile.assets.title"),
          tabBarIcon: ({ color, size }) => <Ionicons name="cube-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="maintenance"
        options={{
          title: t("mobile.nav.maintenance"),
          tabBarIcon: ({ color, size }) => <Ionicons name="build-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="energie"
        options={{
          title: t("mobile.energy.title"),
          tabBarIcon: ({ color, size }) => <Ionicons name="flash-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
