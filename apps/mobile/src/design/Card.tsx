import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "./colors";

/**
 * Carte sombre à bord subtil (maquette de référence, 06/10/2026) : support
 * visuel commun du tableau de bord et des écrans harmonisés. `onPress`
 * optionnel transforme la carte en zone tactile large (pas de petite cible).
 */
export function Card({
  children,
  onPress,
  style,
}: {
  children: ReactNode;
  onPress?: () => void;
  style?: object;
}) {
  if (onPress) {
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [styles.card, pressed && styles.cardPressed, style]}
        accessibilityRole="button"
      >
        {children}
      </Pressable>
    );
  }
  return <View style={[styles.card, style]}>{children}</View>;
}

/**
 * Pastille KPI du tableau de bord Accueil : un nombre réel uniquement,
 * jamais une estimation présentée comme un compte exact.
 */
export function KpiTile({
  label,
  value,
  onPress,
}: {
  label: string;
  value: number | null;
  onPress?: () => void;
}) {
  return (
    <Card onPress={onPress} style={styles.kpiTile}>
      <Text style={styles.kpiValue}>{value === null ? "—" : value}</Text>
      <Text style={styles.kpiLabel}>{label}</Text>
    </Card>
  );
}

/**
 * Bouton d'action rapide (grille Accueil) : icône + libellé, cible tactile
 * large. N'expose que des destinations réelles — jamais une action qui ne
 * mène nulle part.
 */
export function QuickAction({
  label,
  icon,
  onPress,
}: {
  label: string;
  icon: ReactNode;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.quickAction, pressed && styles.cardPressed]}
      accessibilityRole="button"
    >
      <View style={styles.quickActionIcon}>{icon}</View>
      <Text style={styles.quickActionLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    padding: 16,
  },
  cardPressed: {
    backgroundColor: colors.surfaceRaised,
  },
  kpiTile: {
    flexGrow: 1,
    flexBasis: "45%",
    gap: 4,
  },
  kpiValue: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: "700",
  },
  kpiLabel: {
    color: colors.textMuted,
    fontSize: 13,
  },
  quickAction: {
    flexGrow: 1,
    flexBasis: "45%",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 12,
    alignItems: "center",
    gap: 8,
    minHeight: 88,
    justifyContent: "center",
  },
  quickActionIcon: {
    alignItems: "center",
    justifyContent: "center",
  },
  quickActionLabel: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
  },
});
