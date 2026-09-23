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
import {
  CLOSURE_CODES,
  type ClosureDraft,
  type ClosureSection,
  EMPTY_CLOSURE,
  toClosureBody,
  validateClosure,
} from "../src/lib/closure";
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
  const [closeNow, setCloseNow] = useState(false);
  const [closure, setClosure] = useState<ClosureDraft>(EMPTY_CLOSURE);

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
    if (closeNow) {
      const error = validateClosure(closure);
      if (error) {
        Alert.alert(t("mobile.intervention.closure.invalid_title"), t(error));
        return;
      }
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
        closure: closeNow ? toClosureBody(closure) : null,
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

      <View style={styles.checklistRow}>
        <Text style={styles.label}>{t("mobile.intervention.closure.toggle")}</Text>
        <Switch value={closeNow} onValueChange={setCloseNow} />
      </View>
      {closeNow && <ClosureForm draft={closure} onChange={setClosure} />}

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

const SECTIONS: { section: ClosureSection; field: keyof ClosureDraft; label: string }[] = [
  { section: "symptoms", field: "symptom_code", label: "mobile.intervention.closure.symptom" },
  { section: "causes", field: "cause_code", label: "mobile.intervention.closure.cause" },
  { section: "actions", field: "action_code", label: "mobile.intervention.closure.action" },
  {
    section: "verification_results",
    field: "verification_result",
    label: "mobile.intervention.closure.verification",
  },
];

/** Clôture structurée : choix fermés, lisibles avec des gants (ISO 14224). */
function ClosureForm({
  draft,
  onChange,
}: {
  draft: ClosureDraft;
  onChange: (draft: ClosureDraft) => void;
}) {
  const update = (change: Partial<ClosureDraft>) => onChange({ ...draft, ...change });
  const updatePart = (index: number, change: Partial<ClosureDraft["parts"][number]>) =>
    update({
      parts: draft.parts.map((part, i) => (i === index ? { ...part, ...change } : part)),
    });

  return (
    <View style={styles.closure}>
      <Text style={styles.sectionTitle}>{t("mobile.intervention.closure.section")}</Text>
      {SECTIONS.map(({ section, field, label }) => (
        <View key={section}>
          <Text style={styles.label}>{t(label)}</Text>
          <View style={styles.choices}>
            {CLOSURE_CODES[section].map((code) => (
              <Pressable
                key={code}
                onPress={() => update({ [field]: code } as Partial<ClosureDraft>)}
                style={[styles.choice, draft[field] === code && styles.choiceSelected]}
              >
                <Text>{t(`closure.${section}.${code}`)}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ))}

      <Text style={styles.label}>{t("mobile.intervention.closure.labor_minutes")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="number-pad"
        value={draft.labor_minutes}
        onChangeText={(labor_minutes) => update({ labor_minutes })}
      />

      <Text style={styles.label}>{t("mobile.intervention.closure.parts")}</Text>
      {draft.parts.map((part, index) => (
        <View key={index} style={styles.partRow}>
          <TextInput
            style={[styles.input, styles.partReference]}
            placeholder={t("mobile.intervention.closure.part_reference")}
            autoCapitalize="characters"
            value={part.reference}
            onChangeText={(reference) => updatePart(index, { reference })}
          />
          <TextInput
            style={[styles.input, styles.partQuantity]}
            placeholder={t("mobile.intervention.closure.part_quantity")}
            keyboardType="decimal-pad"
            value={part.quantity}
            onChangeText={(quantity) => updatePart(index, { quantity })}
          />
          <Button
            title={t("mobile.intervention.closure.remove_part")}
            onPress={() => update({ parts: draft.parts.filter((_, i) => i !== index) })}
          />
        </View>
      ))}
      <Button
        title={t("mobile.intervention.closure.add_part")}
        onPress={() => update({ parts: [...draft.parts, { reference: "", quantity: "1" }] })}
      />

      <Text style={styles.label}>{t("mobile.intervention.closure.note")}</Text>
      <TextInput
        style={styles.textInput}
        multiline
        value={draft.note}
        onChangeText={(note) => update({ note })}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  closure: {
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: "#eee",
    paddingTop: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  choices: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 4,
  },
  choice: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 16,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  choiceSelected: {
    borderColor: "#2563eb",
    backgroundColor: "#dbeafe",
  },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 10,
  },
  partRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  partReference: {
    flex: 2,
  },
  partQuantity: {
    flex: 1,
  },
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
