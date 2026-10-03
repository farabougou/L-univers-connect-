"use client";

import Link from "next/link";
import { useState } from "react";

import { ACTIVITY_KINDS, filterActivityEntries, type ActivityFeedEntry, type ActivityKind } from "@/lib/activity";
import { colors } from "@/lib/formStyles";

/**
 * Seul composant client du bloc « Activité récente » (directive UI/
 * dashboard, section 16) : le filtre par catégorie est la seule
 * interaction — tout le reste (fusion des sources, tri, traduction des
 * dates) est déjà fait côté serveur (voir apps/web/src/lib/activity.ts).
 * « La timeline doit être lisible et filtrable » : lisible par la liste
 * unique triée par date, filtrable par ces jetons.
 */
export function RecentActivityFeed({
  entries,
  kindLabels,
  emptyLabel,
}: {
  entries: ActivityFeedEntry[];
  kindLabels: Record<ActivityKind, string>;
  emptyLabel: string;
}) {
  const [activeKinds, setActiveKinds] = useState<Set<ActivityKind>>(new Set(ACTIVITY_KINDS));
  const visible = filterActivityEntries(entries, activeKinds);

  function toggle(kind: ActivityKind) {
    setActiveKinds((previous) => {
      const next = new Set(previous);
      if (next.has(kind)) {
        next.delete(kind);
      } else {
        next.add(kind);
      }
      return next;
    });
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {ACTIVITY_KINDS.map((kind) => {
          const active = activeKinds.has(kind);
          return (
            <button
              key={kind}
              type="button"
              onClick={() => toggle(kind)}
              aria-pressed={active}
              style={{
                cursor: "pointer",
                borderRadius: 999,
                border: `1px solid ${active ? colors.accent : colors.border}`,
                padding: "4px 12px",
                fontSize: 12,
                fontWeight: 600,
                background: active ? colors.accentStrong : colors.surface,
                color: active ? "white" : colors.textMuted,
              }}
            >
              {kindLabels[kind]}
            </button>
          );
        })}
      </div>
      {visible.length === 0 ? (
        <p style={{ color: colors.textMuted, fontSize: 13 }}>{emptyLabel}</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
          {visible.map((entry) => (
            <li
              key={entry.key}
              style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 13 }}
            >
              <span>
                <strong>{kindLabels[entry.kind]}</strong>
                {" — "}
                {entry.locationId && entry.locationLabel ? (
                  <Link href={`/registre/${entry.locationId}`} style={{ color: colors.accent }}>
                    {entry.locationLabel}
                  </Link>
                ) : (
                  "—"
                )}
                {entry.title ? ` — ${entry.title}` : ""}
              </span>
              <span style={{ color: colors.textMuted, whiteSpace: "nowrap" }}>{entry.formattedAt}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
