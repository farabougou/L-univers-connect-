import Link from "next/link";

import { ScannerPanel } from "@/components/ScannerPanel";
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import {
  cardStyle,
  colors,
  fieldStyle,
  labelStyle,
  pageContainerStyle,
  submitStyle,
} from "@/lib/formStyles";

import { lookupTag } from "./actions";

/**
 * Point d'entrée web vers le passeport d'un équipement par étiquette
 * (07/10/2026, demande explicite de Mohamed) : un code tapé à la main ou un
 * QR scanné par la caméra du navigateur résolvent tous deux vers la même
 * fiche déjà existante (`/registre/[id]`) — aucune vue passeport dupliquée.
 * Jusqu'ici cette résolution n'existait que côté application mobile
 * (ADR 014 §11) ; le web ne faisait que générer/imprimer l'étiquette.
 */
export default async function PasseportPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { t } = await getTranslator();
  const locale = await getLocale();
  const { error } = await searchParams;
  // "TAG_INVALID_CODE" n'existe pas côté serveur (jamais renvoyé par
  // l'API) : validation de forme uniquement, faite avant l'appel réseau
  // (voir ./actions.ts, parseTagCode) — son message vient donc d'ici, pas
  // du catalogue d'erreurs partagé avec le backend.
  const errorText =
    error === "TAG_INVALID_CODE"
      ? t("web.passport_page.code_invalid")
      : error
        ? (errorMessage(locale, error) ?? t("web.passport_page.lookup_failed"))
        : null;

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>{t("web.passport_page.title")}</h1>

      <section style={cardStyle}>
        <p style={{ color: colors.textMuted }}>{t("web.passport_page.intro")}</p>

        <form action={lookupTag} style={{ maxWidth: 400, marginTop: 16 }}>
          <label style={labelStyle}>
            {t("web.passport_page.code_label")}
            <input
              name="code"
              required
              autoCapitalize="off"
              autoCorrect="off"
              placeholder={t("web.passport_page.code_placeholder")}
              style={fieldStyle}
            />
          </label>
          <button type="submit" style={submitStyle}>
            {t("web.passport_page.submit")}
          </button>
        </form>

        <ScannerPanel
          action={lookupTag}
          scanLabel={t("web.passport_page.scan")}
          cancelLabel={t("web.passport_page.scan_cancel")}
          hintLabel={t("web.passport_page.scan_hint")}
          deniedMessage={t("web.passport_page.camera_denied")}
          unsupportedMessage={t("web.passport_page.camera_unsupported")}
        />

        {errorText && <p style={{ color: colors.danger, marginTop: 16 }}>{errorText}</p>}
      </section>
    </main>
  );
}
