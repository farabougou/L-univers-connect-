import Link from "next/link";

import { apiFetch, requireAccessToken } from "@/lib/api";

import { createWorkOrder } from "./actions";

type WorkOrder = {
  id: string;
  title: string;
  work_order_type: string;
  priority: string;
  status: string;
};

const cellStyle = { borderBottom: "1px solid #eee", padding: "6px 8px", textAlign: "left" as const };
const headerCellStyle = { borderBottom: "1px solid #ddd", padding: "6px 8px", textAlign: "left" as const };
const fieldStyle = { display: "block", width: "100%", padding: 8, marginTop: 4 };

export default async function WorkOrdersPage() {
  const accessToken = await requireAccessToken();
  const response = await apiFetch("/work-orders", accessToken);
  const workOrders: WorkOrder[] = response.ok ? await response.json() : [];

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
      <Link href="/">← Retour</Link>
      <h1>Ordres de travail</h1>

      {workOrders.length === 0 ? (
        <p>Aucun ordre de travail pour l&apos;instant.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 32 }}>
          <thead>
            <tr>
              <th style={headerCellStyle}>Titre</th>
              <th style={headerCellStyle}>Type</th>
              <th style={headerCellStyle}>Priorité</th>
              <th style={headerCellStyle}>Statut</th>
            </tr>
          </thead>
          <tbody>
            {workOrders.map((workOrder) => (
              <tr key={workOrder.id}>
                <td style={cellStyle}>{workOrder.title}</td>
                <td style={cellStyle}>{workOrder.work_order_type}</td>
                <td style={cellStyle}>{workOrder.priority}</td>
                <td style={cellStyle}>{workOrder.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Créer un ordre de travail</h2>
      <form action={createWorkOrder} style={{ maxWidth: 400 }}>
        <label>
          Titre
          <input name="title" required style={fieldStyle} />
        </label>
        <label style={{ display: "block", marginTop: 12 }}>
          Type
          <select name="work_order_type" defaultValue="corrective" style={fieldStyle}>
            <option value="corrective">Correctif</option>
            <option value="preventive">Préventif</option>
            <option value="predictive">Prédictif</option>
            <option value="inspection">Inspection</option>
          </select>
        </label>
        <label style={{ display: "block", marginTop: 12 }}>
          Priorité
          <select name="priority" defaultValue="medium" style={fieldStyle}>
            <option value="low">Basse</option>
            <option value="medium">Moyenne</option>
            <option value="high">Haute</option>
            <option value="urgent">Urgente</option>
          </select>
        </label>
        <button
          type="submit"
          style={{
            marginTop: 16,
            padding: "10px 20px",
            background: "#2563eb",
            color: "white",
            border: "none",
            borderRadius: 8,
          }}
        >
          Créer
        </button>
      </form>
    </main>
  );
}
