import Link from "next/link";

import { colors } from "@/lib/formStyles";
import type { PageWindow } from "@/lib/pagination";

type Translate = (key: string, params?: Record<string, string | number>) => string;

/**
 * Pied de page d'une liste paginée : « 51–100 sur 230 » et liens précédent /
 * suivant. Rien n'est affiché quand tout tient sur une page.
 */
export function Pager({
  window,
  basePath,
  t,
}: {
  window: PageWindow;
  basePath: string;
  t: Translate;
}) {
  if (!window.hasPrevious && !window.hasNext) return null;
  return (
    <nav
      aria-label={t("web.pagination.label")}
      style={{
        display: "flex",
        gap: 16,
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 24px",
      }}
    >
      {window.hasPrevious ? (
        <Link href={`${basePath}?page=${window.page - 1}`} style={{ color: colors.accent }}>
          ← {t("web.pagination.previous")}
        </Link>
      ) : (
        <span />
      )}
      <span style={{ color: colors.textMuted }}>
        {t("web.pagination.range", { from: window.from, to: window.to, total: window.total })}
      </span>
      {window.hasNext ? (
        <Link href={`${basePath}?page=${window.page + 1}`} style={{ color: colors.accent }}>
          {t("web.pagination.next")} →
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
