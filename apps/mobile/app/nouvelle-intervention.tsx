import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRouter } from "expo-router";

import { config } from "../src/lib/config";
import { useAuth } from "../src/lib/auth";
import { t } from "../src/lib/i18n";
import { insertPendingIntervention, listCachedFunctionalLocations } from "../src/lib/db";
import type { CachedFunctionalLocation } from "../src/lib/db";
import { takePhoto } from "../src/lib/photos";
import { syncPendingInterventions } from "../src/lib/sync";

// Codes des vérifications (enregistrés tels quels) ; libellés dans le catalogue.
const CHECKLIST_ITEMS = ["pression_ok", "bruit_anormal", "filtre_propre"];

// Sert aussi de référence client côté serveur (anti-doublon) : unique chez
// un même client, tous téléphones confondus. Date + 16 caractères aléatoires.
function localId(): string {
  const random = () => Math.random().toString(36).slice(2, 10).padEnd(8, "0");
  return `local-${Date.now()}-${random()}${random()}`;
}

export default function NouvelleInterventionScreen() {
  const router = useRouter();
  const auth = useAuth();
  const [interventionType, setInterventionType] = useState<"intervention" | "ronde">(
    "intervention",
  );
  const [summary, setSummary] = useState("");
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [photoPath, setPhotoPath] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [locations, setLocations] = useState<CachedFunctionalLocation[]>([]);
  const [functionalLocationId, setFunctionalLocationId] = useState<string | null>(null);

  useEffect(() => {
    listCachedFunctionalLocations().then(setLocations);
  }, []);

  async function handleTakePhoto() {
    const id = localId();
    const path = await takePhoto(id);
    if (path) {
      setPhotoPath(path);
    }
  }

  async function handleSave() {
    if (!photoPath) {
      Alert.alert(
        t("mobile.intervention.photo_required_title"),
        t("mobile.intervention.photo_required_message"),
      );
      return;
    }
    setIsSaving(true);
    try {
      const id = localId();
      await insertPendingIntervention({
        id,
        interventionType,
        summary: summary.trim() || null,
        checklist,
        startedAt: new Date().toISOString(),
        photoPath,
        functionalLocationId,
      });

      // Tentative d'envoi immédiat si le réseau est disponible maintenant ;
      // sinon la ligne reste en attente et sera reprise plus tard (voir
      // ADR 010 et le déclenchement automatique sur l'écran d'accueil).
      const token = await auth.getAccessToken();
      if (token) {
        await syncPendingInterventions(config.apiUrl, token).catch(() => {});
      }

      router.back();
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>{t("mobile.intervention.title")}</Text>

      <View style={styles.typeRow}>
        <Button
          title={t("intervention_type.intervention")}
          onPress={() => setInterventionType("intervention")}
          color={interventionType === "intervention" ? undefined : "#999"}
        />
        <Button
          title={t("intervention_type.ronde")}
          onPress={() => setInterventionType("ronde")}
          color={interventionType === "ronde" ? undefined : "#999"}
        />
      </View>

      <Text style={styles.label}>{t("mobile.intervention.equipment_optional")}</Text>
      {locations.length === 0 ? (
        <Text style={styles.hint}>{t("mobile.intervention.no_cached_equipment")}</Text>
      ) : (
        <View style={styles.locationList}>
          {locations.map((location) => (
            <Pressable
              key={location.id}
              onPress={() =>
                setFunctionalLocationId((current) =>
                  current === location.id ? null : location.id,
                )
              }
              style={[
                styles.locationItem,
                functionalLocationId === location.id && styles.locationItemSelected,
              ]}
            >
              <Text>
                {location.code} — {location.name}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      <Text style={styles.label}>{t("mobile.intervention.summary")}</Text>
      <TextInput
        style={styles.textInput}
        multiline
        placeholder={t("mobile.intervention.summary_placeholder")}
        value={summary}
        onChangeText={setSummary}
      />

      <Text style={styles.label}>{t("mobile.intervention.checks")}</Text>
      {CHECKLIST_ITEMS.map((key) => (
        <View key={key} style={styles.checklistRow}>
          <Text>{t(`mobile.intervention.check.${key}`)}</Text>
          <Switch
            value={checklist[key] ?? false}
            onValueChange={(value) => setChecklist((prev) => ({ ...prev, [key]: value }))}
          />
        </View>
      ))}

      <Text style={styles.label}>{t("mobile.intervention.photo_required_label")}</Text>
      {photoPath && <Image source={{ uri: photoPath }} style={styles.photo} />}
      <Button
        title={t(photoPath ? "mobile.intervention.retake_photo" : "mobile.intervention.take_photo")}
        onPress={handleTakePhoto}
      />

      <View style={styles.saveButton}>
        <Button
          title={t("mobile.intervention.save")}
          onPress={handleSave}
          disabled={!photoPath || isSaving}
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    gap: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: "600",
    marginBottom: 8,
  },
  typeRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 8,
  },
  label: {
    fontWeight: "600",
    marginTop: 12,
  },
  textInput: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 12,
    minHeight: 80,
    textAlignVertical: "top",
  },
  hint: {
    color: "#666",
    fontStyle: "italic",
  },
  locationList: {
    gap: 6,
  },
  locationItem: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 10,
  },
  locationItemSelected: {
    borderColor: "#2563eb",
    backgroundColor: "#eff6ff",
  },
  checklistRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
  },
  photo: {
    width: "100%",
    height: 200,
    borderRadius: 8,
    marginBottom: 8,
  },
  saveButton: {
    marginTop: 24,
  },
});
