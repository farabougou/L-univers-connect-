import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="nouvelle-intervention" options={{ title: "Nouvelle intervention" }} />
      <Stack.Screen name="historique" options={{ title: "Historique" }} />
      <Stack.Screen name="passeport" options={{ title: "Passeport équipement" }} />
    </Stack>
  );
}
