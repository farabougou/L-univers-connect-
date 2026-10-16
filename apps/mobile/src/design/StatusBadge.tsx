import { StyleSheet, Text, View } from "react-native";

import { ASSET_STATUS_COLOR, ASSET_STATUS_GLYPH, type AssetStatus, SEVERITY_COLOR } from "./colors";

/**
 * Pastille d'état générique (équivalent mobile de StatusBadge côté web,
 * apps/web/src/components/StatusBadge.tsx). Toujours fournie déjà traduite
 * (`label`) : ce composant ne connaît aucun texte, uniquement la couleur.
 * Taille de police et marges volontairement plus grandes que côté web
 * (lecture terrain, pas un écran de bureau).
 */
function Badge({ color, label, glyph }: { color: string; label: string; glyph?: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: color }]} accessibilityRole="text">
      {glyph && <Text style={styles.glyph}>{glyph}</Text>}
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

/** Gravité d'une alarme ou d'un constat (`severity.*`) — déjà traduite. */
export function SeverityBadge({ severity, label }: { severity: string; label: string }) {
  return <Badge color={SEVERITY_COLOR[severity] ?? SEVERITY_COLOR.info} label={label} />;
}

/**
 * État d'un actif (opérationnel/communication/fraîcheur), même vocabulaire
 * que le web (`equipmentStatusToAssetStatus`). Un glyphe accompagne
 * toujours la couleur (ADR 013, accessibilité : jamais la couleur seule).
 */
export function AssetStatusBadge({ status, label }: { status: AssetStatus; label: string }) {
  return <Badge color={ASSET_STATUS_COLOR[status]} label={label} glyph={ASSET_STATUS_GLYPH[status]} />;
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 6,
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 12,
  },
  glyph: {
    color: "white",
    fontSize: 13,
  },
  label: {
    color: "white",
    fontSize: 14,
    fontWeight: "700",
  },
});
