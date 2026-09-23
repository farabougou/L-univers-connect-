import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Button, StyleSheet, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import NetInfo from "@react-native-community/netinfo";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { countPendingInterventions } from "../src/lib/db";
import { refreshFunctionalLocationsCache, syncPendingInterventions } from "../src/lib/sync";

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
    await syncPendingInterventions(config.apiUrl, token);
    await refreshFunctionalLocationsCache(config.apiUrl, token).catch(() => {});
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
        <Text style={styles.title}>Physical Asset Intelligence OS</Text>
        <Text style={styles.subtitle}>Application technicien</Text>
        <Button title="Se connecter" onPress={auth.signIn} disabled={!auth.canSignIn} />
        {auth.error && <Text style={styles.error}>{auth.error}</Text>}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Connecté</Text>
      {me && (
        <>
          <Text>Utilisateur : {me.sub}</Text>
          <Text>Tenant : {me.tenant_id}</Text>
          <Text>Rôles : {me.roles.join(", ")}</Text>
        </>
      )}
      {apiError && <Text style={styles.error}>Erreur API : {apiError}</Text>}

      <Button
        title="Nouvelle intervention"
        onPress={() => router.push("/nouvelle-intervention")}
      />
      <Button title="Historique" onPress={() => router.push("/historique")} />
      <Button title="Passeport équipement" onPress={() => router.push("/passeport")} />

      <Text>
        {pendingCount > 0
          ? `${pendingCount} en attente d'envoi`
          : "Rien en attente d'envoi"}
      </Text>
      {pendingCount > 0 && <Button title="Synchroniser" onPress={runSync} />}

      <Button title="Se déconnecter" onPress={auth.signOut} />
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
