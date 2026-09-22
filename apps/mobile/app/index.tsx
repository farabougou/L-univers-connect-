import { useEffect, useState } from "react";
import { ActivityIndicator, Button, StyleSheet, Text, View } from "react-native";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";

type MeResponse = {
  sub: string;
  tenant_id: string;
  roles: string[];
};

export default function HomeScreen() {
  const auth = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (!auth.accessToken) {
      setMe(null);
      return;
    }
    setApiError(null);
    fetch(`${config.apiUrl}/me`, {
      headers: { Authorization: `Bearer ${auth.accessToken}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(setMe)
      .catch((err: Error) => setApiError(err.message));
  }, [auth.accessToken]);

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
