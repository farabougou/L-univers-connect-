import { Suspense } from "react";

import { getTranslator } from "@/lib/i18n";

import { LoginError } from "./LoginError";

export default async function LoginPage() {
  const { t } = await getTranslator();
  return (
    <main style={{ maxWidth: 420, margin: "80px auto", textAlign: "center" }}>
      <h1>{t("common.app_name")}</h1>
      <p>{t("web.login.subtitle")}</p>
      <Suspense>
        <LoginError message={t("web.login.failed")} />
      </Suspense>
      <a
        href="/api/auth/login"
        style={{
          display: "inline-block",
          marginTop: 24,
          padding: "10px 24px",
          background: "#2563eb",
          color: "white",
          borderRadius: 8,
          textDecoration: "none",
        }}
      >
        {t("common.sign_in")}
      </a>
    </main>
  );
}
