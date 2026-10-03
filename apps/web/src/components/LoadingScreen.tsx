import { getTranslator } from "@/lib/i18n";
import { colors, pageContainerStyle } from "@/lib/formStyles";

/**
 * État de chargement partagé par chaque segment (voir les fichiers
 * `loading.tsx`, convention Next.js) : jusqu'au 02/10/2026, un écran lent ne
 * montrait rien — ni squelette ni indicateur — pendant que la page serveur
 * attendait l'API, contrairement à la directive produit (vrais états
 * chargement/vide/erreur, jamais rien).
 */
export async function LoadingScreen() {
  const { t } = await getTranslator();
  return (
    <main style={pageContainerStyle}>
      <div
        role="status"
        style={{ display: "flex", alignItems: "center", gap: 12, color: colors.textMuted }}
      >
        <span className="loading-spinner" aria-hidden="true" />
        <span>{t("common.loading")}</span>
      </div>
    </main>
  );
}
