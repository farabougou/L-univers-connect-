import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  TextInput,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

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
import {
  emptyFgas,
  FGAS_CODES,
  type FgasDraft,
  type FgasSection,
  toFgasBody,
  validateFgas,
} from "../src/lib/fgas";
import { takePhoto } from "../src/lib/photos";
import { synchronize } from "../src/lib/sync";
import { colors } from "../src/design/colors";
import { Text } from "../src/design/Text";

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
  // Arrivée depuis le passeport d'un équipement (ordre de travail ou alarme
  // en cours) : relie l'intervention à ce qui l'a déclenchée au lieu de
  // laisser le technicien recréer le lien de mémoire (voir
  // app/passeport.tsx — trouvé manquant par l'audit de bout en bout du
  // 02/10/2026, le modèle serveur l'acceptait déjà sans qu'aucun écran ne
  // le propose).
  const params = useLocalSearchParams<{
    workOrderId?: string;
    workOrderTitle?: string;
    functionalLocationId?: string;
  }>();
  const workOrderId = params.workOrderId ?? null;
  const [interventionType, setInterventionType] = useState<"intervention" | "ronde">(
    "intervention",
  );
  const [summary, setSummary] = useState("");
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [photoPath, setPhotoPath] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [locations, setLocations] = useState<CachedFunctionalLocation[]>([]);
  const [functionalLocationId, setFunctionalLocationId] = useState<string | null>(
    params.functionalLocationId ?? null,
  );
  const [closeNow, setCloseNow] = useState(false);
  const [closure, setClosure] = useState<ClosureDraft>(EMPTY_CLOSURE);
  const [fgasNow, setFgasNow] = useState(false);
  const [fgas, setFgas] = useState<FgasDraft>(emptyFgas());

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
    if (fgasNow) {
      const error = validateFgas(fgas);
      if (error) {
        Alert.alert(t("mobile.intervention.fgas.invalid_title"), t(error));
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
        fgas: fgasNow ? toFgasBody(fgas) : null,
        workOrderId,
      });

      // Tentative d'envoi immédiat si le réseau est disponible maintenant ;
      // sinon la ligne reste en attente et sera reprise plus tard (voir
      // ADR 010 et le déclenchement automatique sur l'écran d'accueil).
      // synchronize() partage un même verrou avec l'écran d'accueil : les
      // deux ne peuvent jamais écrire dans la base locale en même temps.
      const token = await auth.getAccessToken();
      if (token) {
        await synchronize(config.apiUrl, token).catch(() => {});
      }

      router.back();
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>{t("mobile.intervention.title")}</Text>

      {workOrderId && params.workOrderTitle && (
        <Text style={styles.hint}>
          {t("mobile.intervention.linked_work_order", { title: params.workOrderTitle })}
        </Text>
      )}

      <View style={styles.typeRow}>
        <Button
          title={t("intervention_type.intervention")}
          onPress={() => setInterventionType("intervention")}
          color={interventionType === "intervention" ? undefined : colors.inactive}
        />
        <Button
          title={t("intervention_type.ronde")}
          onPress={() => setInterventionType("ronde")}
          color={interventionType === "ronde" ? undefined : colors.inactive}
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
        placeholderTextColor={colors.textMuted}
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

      <View style={styles.checklistRow}>
        <Text style={styles.label}>{t("mobile.intervention.fgas.toggle")}</Text>
        <Switch value={fgasNow} onValueChange={setFgasNow} />
      </View>
      {fgasNow && <FgasForm draft={fgas} onChange={setFgas} />}

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
            placeholderTextColor={colors.textMuted}
            autoCapitalize="characters"
            value={part.reference}
            onChangeText={(reference) => updatePart(index, { reference })}
          />
          <TextInput
            style={[styles.input, styles.partQuantity]}
            placeholder={t("mobile.intervention.closure.part_quantity")}
            placeholderTextColor={colors.textMuted}
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

const MULTI_SELECT_SECTIONS: { section: FgasSection; field: keyof FgasDraft; label: string }[] = [
  {
    section: "nature_of_intervention",
    field: "nature_of_intervention",
    label: "mobile.intervention.fgas.nature",
  },
  {
    section: "waste_classification",
    field: "waste_classification",
    label: "mobile.intervention.fgas.waste_classification",
  },
];

/**
 * Fiche d'intervention fluides frigorigènes fluorés (CERFA 15497*04) :
 * mêmes champs que l'API (app/fgas.py), organisés dans l'ordre du
 * formulaire officiel. Les totaux de manipulation ([11], A+B+C et D+E) ne
 * sont pas saisis ici : le serveur les calcule à partir de leurs
 * composants (jamais une incohérence possible comme sur le papier).
 */
function FgasForm({ draft, onChange }: { draft: FgasDraft; onChange: (draft: FgasDraft) => void }) {
  const update = (change: Partial<FgasDraft>) => onChange({ ...draft, ...change });
  const toggleCode = (field: "nature_of_intervention" | "waste_classification", code: string) => {
    const current = draft[field];
    update({
      [field]: current.includes(code)
        ? current.filter((c) => c !== code)
        : [...current, code],
    } as Partial<FgasDraft>);
  };
  const updateLeak = (index: number, change: Partial<FgasDraft["leaks"][number]>) =>
    update({
      leaks: draft.leaks.map((leak, i) => (i === index ? { ...leak, ...change } : leak)),
    });

  return (
    <View style={styles.closure}>
      <Text style={styles.sectionTitle}>{t("mobile.intervention.fgas.section")}</Text>

      <Text style={styles.label}>{t("mobile.intervention.fgas.operator_name")}</Text>
      <TextInput
        style={styles.input}
        value={draft.operator_name}
        onChangeText={(operator_name) => update({ operator_name })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.operator_capacity_number")}</Text>
      <TextInput
        style={styles.input}
        value={draft.operator_capacity_number}
        onChangeText={(operator_capacity_number) => update({ operator_capacity_number })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.detenteur_name")}</Text>
      <TextInput
        style={styles.input}
        value={draft.detenteur_name}
        onChangeText={(detenteur_name) => update({ detenteur_name })}
      />

      <Text style={styles.label}>{t("mobile.intervention.fgas.equipment_identification")}</Text>
      <TextInput
        style={styles.input}
        value={draft.equipment_identification}
        onChangeText={(equipment_identification) => update({ equipment_identification })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.refrigerant_name")}</Text>
      <TextInput
        style={styles.input}
        autoCapitalize="characters"
        value={draft.refrigerant_name}
        onChangeText={(refrigerant_name) => update({ refrigerant_name })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.total_charge_kg")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        value={draft.total_charge_kg}
        onChangeText={(total_charge_kg) => update({ total_charge_kg })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.co2_equivalent_tonnes")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        value={draft.co2_equivalent_tonnes}
        onChangeText={(co2_equivalent_tonnes) => update({ co2_equivalent_tonnes })}
      />

      {MULTI_SELECT_SECTIONS.map(({ section, field, label }) => (
        <View key={section}>
          <Text style={styles.label}>{t(label)}</Text>
          <View style={styles.choices}>
            {FGAS_CODES[section].map((code) => {
              const selected = (draft[field] as string[]).includes(code);
              return (
                <Pressable
                  key={code}
                  onPress={() => toggleCode(field as "nature_of_intervention" | "waste_classification", code)}
                  style={[styles.choice, selected && styles.choiceSelected]}
                >
                  <Text>{t(`fgas.${section}.${code}`)}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ))}
      {draft.nature_of_intervention.includes("other") && (
        <>
          <Text style={styles.label}>{t("mobile.intervention.fgas.nature_other_detail")}</Text>
          <TextInput
            style={styles.input}
            value={draft.nature_other_detail}
            onChangeText={(nature_other_detail) => update({ nature_other_detail })}
          />
        </>
      )}

      <Text style={styles.label}>{t("mobile.intervention.fgas.leaks_found")}</Text>
      <Switch
        value={draft.leaks_found ?? false}
        onValueChange={(leaks_found) => update({ leaks_found })}
      />
      {draft.leaks_found && (
        <>
          {draft.leaks.map((leak, index) => (
            <View key={index} style={styles.partRow}>
              <TextInput
                style={[styles.input, styles.partReference]}
                placeholder={t("mobile.intervention.fgas.leak_location")}
                placeholderTextColor={colors.textMuted}
                value={leak.location}
                onChangeText={(location) => updateLeak(index, { location })}
              />
              <Switch
                value={leak.repaired ?? false}
                onValueChange={(repaired) => updateLeak(index, { repaired })}
              />
              <Button
                title={t("mobile.intervention.closure.remove_part")}
                onPress={() => update({ leaks: draft.leaks.filter((_, i) => i !== index) })}
              />
            </View>
          ))}
          <Button
            title={t("mobile.intervention.fgas.add_leak")}
            onPress={() =>
              update({ leaks: [...draft.leaks, { location: "", repaired: false }] })
            }
          />
        </>
      )}

      <Text style={styles.label}>{t("mobile.intervention.fgas.charged_virgin_kg")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        value={draft.charged_virgin_kg}
        onChangeText={(charged_virgin_kg) => update({ charged_virgin_kg })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.charged_recycled_kg")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        value={draft.charged_recycled_kg}
        onChangeText={(charged_recycled_kg) => update({ charged_recycled_kg })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.charged_regenerated_kg")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        value={draft.charged_regenerated_kg}
        onChangeText={(charged_regenerated_kg) => update({ charged_regenerated_kg })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.recovered_for_treatment_kg")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        value={draft.recovered_for_treatment_kg}
        onChangeText={(recovered_for_treatment_kg) => update({ recovered_for_treatment_kg })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.recovered_for_reuse_kg")}</Text>
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        value={draft.recovered_for_reuse_kg}
        onChangeText={(recovered_for_reuse_kg) => update({ recovered_for_reuse_kg })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.bsff_number")}</Text>
      <TextInput
        style={styles.input}
        value={draft.bsff_number}
        onChangeText={(bsff_number) => update({ bsff_number })}
      />

      <Text style={styles.label}>{t("mobile.intervention.fgas.observations")}</Text>
      <TextInput
        style={styles.textInput}
        multiline
        value={draft.observations}
        onChangeText={(observations) => update({ observations })}
      />

      <Text style={styles.label}>{t("mobile.intervention.fgas.operator_signatory_name")}</Text>
      <TextInput
        style={styles.input}
        value={draft.operator_signatory_name}
        onChangeText={(operator_signatory_name) => update({ operator_signatory_name })}
      />
      <Text style={styles.label}>{t("mobile.intervention.fgas.signed_at")}</Text>
      <TextInput
        style={styles.input}
        placeholder="2026-10-02"
        value={draft.signed_at}
        onChangeText={(signed_at) => update({ signed_at })}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  closure: {
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
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
    borderColor: colors.border,
    borderRadius: 16,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  choiceSelected: {
    borderColor: colors.selectedBorder,
    backgroundColor: colors.selectedBackground,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
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
    borderColor: colors.border,
    borderRadius: 8,
    padding: 12,
    minHeight: 80,
    textAlignVertical: "top",
    color: colors.textPrimary,
    backgroundColor: colors.surface,
  },
  hint: {
    color: colors.textMuted,
    fontStyle: "italic",
  },
  locationList: {
    gap: 6,
  },
  locationItem: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
  },
  locationItemSelected: {
    borderColor: colors.selectedBorder,
    backgroundColor: colors.selectedBackground,
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
