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
