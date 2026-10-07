import { type ReactNode, useState } from "react";
import { StyleSheet, View } from "react-native";

import { colors } from "./colors";
import { AppDrawer } from "./Drawer";
import { TopBar } from "./TopBar";

/**
 * Carcasse commune des écrans d'onglet (Accueil, Actifs, Maintenance,
 * Énergie) : barre compacte + tiroir superposé, jamais une sidebar
 * permanente (maquette de référence, 06/10/2026). Les écrans empilés
 * (Passeport, Alertes, Profil, Ajouter un site) gardent l'en-tête natif de
 * la navigation Stack — ils s'ouvrent depuis cette barre, pas depuis eux-
 * mêmes.
 */
export function Screen({ children, alertCount }: { children: ReactNode; alertCount?: number | null }) {
  const [drawerVisible, setDrawerVisible] = useState(false);
  return (
    <View style={styles.container}>
      <TopBar onOpenDrawer={() => setDrawerVisible(true)} alertCount={alertCount} />
      <View style={styles.content}>{children}</View>
      <AppDrawer visible={drawerVisible} onClose={() => setDrawerVisible(false)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
  },
});
