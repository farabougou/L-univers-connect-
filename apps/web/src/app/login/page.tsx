import { Suspense } from "react";

import { BrandMark } from "@/components/BrandMark";
import { getTranslator } from "@/lib/i18n";

import { LoginError } from "./LoginError";

export default async function LoginPage() {
  const { t } = await getTranslator();
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#050b1a",
        padding: 16,
      }}
    >
      <div style={{ maxWidth: 380, width: "100%", textAlign: "center" }}>
        <BrandMark size={96} label={t("common.app_name")} />
        <h1
          style={{
            marginTop: 20,
            fontSize: 30,
            fontWeight: 700,
            letterSpacing: "0.08em",
            color: "#f8fafc",
          }}
        >
          {t("common.app_name").toUpperCase()}
        </h1>
        <p style={{ marginTop: 4, color: "#7dd3fc", fontSize: 13, letterSpacing: "0.04em" }}>
          {t("common.tagline")}
        </p>
        <p style={{ marginTop: 24, color: "#94a3b8" }}>{t("web.login.subtitle")}</p>
        <Suspense>
          <LoginError message={t("web.login.failed")} />
        </Suspense>
        <a
          href="/api/auth/login"
          style={{
            display: "inline-block",
            marginTop: 24,
            padding: "12px 32px",
            background: "linear-gradient(135deg, #38bdf8, #1d4ed8)",
            color: "white",
            fontWeight: 600,
            borderRadius: 10,
            textDecoration: "none",
            boxShadow: "0 8px 24px rgba(29, 78, 216, 0.35)",
          }}
        >
          {t("common.sign_in")}
        </a>
      </div>
    </main>
  );
}
