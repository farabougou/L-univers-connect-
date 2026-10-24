import Link from "next/link";

import { colors } from "@/lib/formStyles";
import { isArchivedLocation, type LocationRecord } from "@/lib/locations";

/**
 * Équipement d'une ligne d'alarme, de constat, d'ordre de travail, de mesure ou de
 * consommation : « CODE — Nom », avec un lien vers sa fiche. Un équipement archivé reste
 * nommé et porte la mention « archivé » en toutes lettres (jamais la couleur seule). Sans
 * équipement connu, le tiret : le système n'invente rien.
 */
export function EquipmentLink({
  location,
  t,
  link = true,
  codeOnly = false,
}: {
  location: (LocationRecord & { code: string; name: string }) | undefined;
  t: (key: string, params?: Record<string, string>) => string;
  link?: boolean;
  codeOnly?: boolean;
}) {
  if (!location) {
    return <>—</>;
  }
  const label = codeOnly ? location.code : `${location.code} — ${location.name}`;
  return (
    <>
      {link ? (
        <Link href={`/registre/${location.id}`} style={{ color: colors.accent }}>
          {label}
        </Link>
      ) : (
        label
      )}
      {isArchivedLocation(location) && (
        <>
          {" "}
          <span style={{ color: colors.textMuted }}>· {t("common.archived")}</span>
        </>
      )}
    </>
  );
}
