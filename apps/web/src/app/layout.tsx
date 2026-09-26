import type { Metadata } from "next";
import "./globals.css";

import { getLocale, getTranslator } from "@/lib/i18n";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getTranslator();
  return { title: "PAIOS", description: `${t("common.app_name")} — ${t("web.console")}` };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={await getLocale()}>
      <body>{children}</body>
    </html>
  );
}
