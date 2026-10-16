import { useEffect, useState } from "react";
import { ActivityIndicator, Button, StyleSheet, View } from "react-native";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { t } from "../src/lib/i18n";
import { fetchMe, type Me } from "../src/lib/me";
import { roleLabels } from "../src/lib/roles";
import { colors } from "../src/design/colors";
import { Card } from "../src/design/Card";
import { Text } from "../src/design/Text";

/**
 * Profil (maquette de référence, 06/10/2026) : vraies données `/me`,
 * remplace le bouton de déconnexion isolé qui vivait jusqu'ici au bas de
 * l'accueil — même source que l'ancien écran (app/index.tsx avant la
 * refonte).
 */
export default function ProfilScreen() {
  const auth = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth.accessToken) return;
    let cancelled = false;
    auth.getAccessToken().then(async (token) => {
      if (!token) return;
      const result = await fetchMe(config.apiUrl, token);
      if (cancelled) return;
      if (result) {
        setMe(result);
      } else {
        setError(t("mobile.profile.load_failed"));
      }
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [auth.accessToken]);

  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      {me && (
        <Card style={styles.card}>
          <Text style={styles.row}>{t("mobile.home.user", { user: me.sub })}</Text>
          {me.tenant_name && (
            <Text style={styles.row}>{t("mobile.home.tenant", { tenant: me.tenant_name })}</Text>
          )}
          <Text style={styles.row}>{t("mobile.home.roles", { roles: roleLabels(me.roles, t) })}</Text>
        </Card>
      )}
      <View style={styles.signOutButton}>
        <Button title={t("common.sign_out")} onPress={auth.signOut} color={colors.danger} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    gap: 16,
    backgroundColor: colors.background,
  },
  card: {
    gap: 8,
  },
  row: {
    fontSize: 15,
  },
  error: {
    color: colors.danger,
  },
  signOutButton: {
    marginTop: 8,
  },
});
