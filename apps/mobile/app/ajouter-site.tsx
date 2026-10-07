import { useState } from "react";
import { Button, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { useRouter } from "expo-router";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { t } from "../src/lib/i18n";
import { createSite } from "../src/lib/sites";
import { colors } from "../src/design/colors";
import { Text } from "../src/design/Text";

/**
 * Ajouter un site (maquette de référence, 06/10/2026) : mêmes champs et
 * même endpoint que le formulaire web (apps/web/src/app/registre/page.tsx,
 * POST /sites) — réservé aux rôles `responsable_exploitation` et
 * `admin_tenant` côté serveur (voir src/lib/sites.ts). Le fuseau horaire
 * est pré-rempli avec celui de l'appareil : un technicien le corrige
 * seulement si le site est ailleurs.
 */
export default function AjouterSiteScreen() {
  const router = useRouter();
  const auth = useAuth();
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone,
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit() {
    if (!name.trim() || !timezone.trim()) return;
    const token = await auth.getAccessToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    const result = await createSite(config.apiUrl, token, name.trim(), timezone.trim());
    setSaving(false);
    if (result.ok) {
      router.back();
      return;
    }
    setError(t(result.messageKey));
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.label}>{t("mobile.add_site.name_label")}</Text>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder={t("mobile.add_site.name_placeholder")}
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>{t("mobile.add_site.timezone_label")}</Text>
      <TextInput
        style={styles.input}
        value={timezone}
        onChangeText={setTimezone}
        placeholder={t("mobile.add_site.timezone_placeholder")}
        placeholderTextColor={colors.textMuted}
        autoCapitalize="none"
        autoCorrect={false}
      />

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.submitButton}>
        <Button
          title={t("mobile.add_site.submit")}
          onPress={handleSubmit}
          disabled={saving || !name.trim() || !timezone.trim()}
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    gap: 8,
  },
  label: {
    fontWeight: "600",
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
  },
  error: {
    color: colors.danger,
    marginTop: 8,
  },
  submitButton: {
    marginTop: 24,
  },
});
