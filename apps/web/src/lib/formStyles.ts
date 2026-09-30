/**
 * Styles réutilisés par les formulaires et tableaux de la console (registre,
 * ordres de travail) : un seul endroit à changer plutôt que trois copies
 * qui finissent par diverger.
 */
export const fieldStyle = { display: "block", width: "100%", padding: 8, marginTop: 4 };
export const labelStyle = { display: "block", marginTop: 12 };
export const submitStyle = {
  marginTop: 16,
  padding: "10px 20px",
  background: "#2563eb",
  color: "white",
  border: "none",
  borderRadius: 8,
};
export const cellStyle = { borderBottom: "1px solid #eee", padding: "6px 8px", textAlign: "left" as const };
export const headerCellStyle = {
  borderBottom: "1px solid #ddd",
  padding: "6px 8px",
  textAlign: "left" as const,
};

/**
 * Socle de design partagé (ADR 014, section « Design System commun ») :
 * un tout petit nombre de jetons et de blocs de présentation réutilisables,
 * pas une bibliothèque de composants. Étendu progressivement, jamais
 * remplacé d'un coup (voir feature-benchmark-matrix.md).
 */
export const colors = {
  pageBackground: "#f8fafc",
  surface: "#ffffff",
  border: "#e5e7eb",
  textPrimary: "#0f172a",
  textMuted: "#64748b",
  accent: "#2563eb",
};

export const pageContainerStyle = {
  maxWidth: 1080,
  margin: "0 auto",
  padding: "32px 20px 64px",
};

export const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 24,
  flexWrap: "wrap" as const,
  gap: 12,
};

export const cardStyle = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: 12,
  padding: "20px 24px",
  boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
};

export const sectionTitleStyle = {
  fontSize: 13,
  fontWeight: 700,
  color: colors.textMuted,
  textTransform: "uppercase" as const,
  letterSpacing: "0.05em",
  marginBottom: 16,
};

export const badgeStyle = (background: string) => ({
  display: "inline-block",
  color: "white",
  background,
  borderRadius: 999,
  padding: "2px 10px",
  fontSize: 12,
  fontWeight: 600,
});
