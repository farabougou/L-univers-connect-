import { Stack } from "expo-router";

import { t } from "../src/lib/i18n";

export default function RootLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="nouvelle-intervention" options={{ title: t("mobile.intervention.title") }} />
      <Stack.Screen name="historique" options={{ title: t("mobile.home.history") }} />
      <Stack.Screen name="passeport" options={{ title: t("mobile.passport.screen_title") }} />
    </Stack>
  );
}
