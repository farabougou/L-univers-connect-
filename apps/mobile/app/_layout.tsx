import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { colors } from "../src/design/colors";
import { t } from "../src/lib/i18n";

/**
 * Les 4 écrans d'onglet (Accueil, Actifs, Maintenance, Énergie) vivent dans
 * le groupe (tabs) et portent leur propre barre compacte + tiroir (voir
 * src/design/Screen.tsx) — jamais d'en-tête natif en double au-dessus. Les
 * écrans ouverts depuis cette barre ou depuis une liste (Passeport,
 * Alertes, Ajouter un site, Profil, Nouvelle intervention) restent des
 * écrans empilés classiques, avec l'en-tête natif (titre + retour).
 */
export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          contentStyle: { backgroundColor: colors.background },
          headerStyle: { backgroundColor: colors.surface },
          headerTintColor: colors.textPrimary,
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="nouvelle-intervention" options={{ title: t("mobile.intervention.title") }} />
        <Stack.Screen name="passeport" options={{ title: t("mobile.passport.screen_title") }} />
        <Stack.Screen name="alertes" options={{ title: t("mobile.alerts.title") }} />
        <Stack.Screen name="ajouter-site" options={{ title: t("mobile.add_site.title") }} />
        <Stack.Screen name="plans" options={{ title: t("mobile.plans.title") }} />
        <Stack.Screen name="profil" options={{ title: t("mobile.profile.title") }} />
      </Stack>
    </>
  );
}
