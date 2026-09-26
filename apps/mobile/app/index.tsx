import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Button, StyleSheet, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import NetInfo from "@react-native-community/netinfo";

import { config } from "../src/lib/config";
import { t } from "../src/lib/i18n";
import { useAuth } from "../src/lib/auth";
import { countPendingInterventions } from "../src/lib/db";
import { synchronize } from "../src/lib/sync";

type MeResponse = {
  sub: string;
  tenant_id: string;
  roles: string[];
};

export default function HomeScreen() {
  const router = useRouter();
  const auth = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    if (!auth.accessToken) {
      setMe(null);
      return;
    }
    setApiError(null);
    auth.getAccessToken().then((token) => {
      if (!token) return;
      fetch(`${config.apiUrl}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => {
          if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
          return res.json();
        })
        .then(setMe)
        .catch((err: Error) => setApiError(err.message));
    });
  }, [auth.accessToken]);

  async function refreshPendingCount() {
    setPendingCount(await countPendingInterventions());
  }

  async function runSync() {
    const token = await auth.getAccessToken();
    if (!token) return;
    await synchronize(config.apiUrl, token);
    await refreshPendingCount();
  }

  // Synchronise dès que le réseau revient, sans attendre une action du
  // technicien : c'est tout l'intérêt du mode hors ligne (voir ADR 010).
  useEffect(() => {
    refreshPendingCount();
    const unsubscribe = NetInfo.addEventListener((state) => {
      if (state.isConnected) {
        runSync();
      }
    });
    return unsubscribe;
  }, [auth.accessToken]);

  useFocusEffect(
    useCallback(() => {
      refreshPendingCount();
    }, []),
  );

  if (auth.isLoading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!auth.accessToken) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>{t("common.app_name")}</Text>
        <Text style={styles.subtitle}>{t("mobile.home.subtitle")}</Text>
        <Button title={t("common.sign_in")} onPress={auth.signIn} disabled={!auth.canSignIn} />
        {auth.error && <Text style={styles.error}>{t(auth.error)}</Text>}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t("mobile.home.signed_in")}</Text>
      {me && (
        <>
          <Text>{t("mobile.home.user", { user: me.sub })}</Text>
          <Text>{t("mobile.home.tenant", { tenant: me.tenant_id })}</Text>
          <Text>{t("mobile.home.roles", { roles: me.roles.join(", ") })}</Text>
        </>
      )}
      {apiError && <Text style={styles.error}>{t("mobile.home.server_unreachable")}</Text>}

      <Button
        title={t("mobile.home.new_intervention")}
        onPress={() => router.push("/nouvelle-intervention")}
      />
      <Button title={t("mobile.home.history")} onPress={() => router.push("/historique")} />
      <Button title={t("mobile.home.passport")} onPress={() => router.push("/passeport")} />

      <Text>
        {pendingCount > 0
          ? t("mobile.home.pending", { count: pendingCount })
          : t("mobile.home.nothing_pending")}
      </Text>
      {pendingCount > 0 && <Button title={t("mobile.home.sync")} onPress={runSync} />}

      <Button title={t("common.sign_out")} onPress={auth.signOut} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    padding: 24,
  },
  title: {
    fontSize: 20,
    fontWeight: "600",
  },
  subtitle: {
    color: "#666",
  },
  error: {
    color: "#c0392b",
  },
});
