import { redirect } from "next/navigation";

import { config } from "@/lib/config";
import { getAccessTokenCookie } from "@/lib/session";

type Me = {
  sub: string;
  tenant_id: string;
  roles: string[];
};

type FunctionalLocation = {
  id: string;
  code: string;
  name: string;
};

export default async function DashboardPage() {
  const accessToken = await getAccessTokenCookie();
  if (!accessToken) {
    redirect("/login");
  }

  const headers = { Authorization: `Bearer ${accessToken}` };
  const [meResponse, locationsResponse] = await Promise.all([
    fetch(`${config.apiUrl}/me`, { headers, cache: "no-store" }),
    fetch(`${config.apiUrl}/functional-locations`, { headers, cache: "no-store" }),
  ]);

  if (!meResponse.ok) {
    redirect("/login");
  }

  const me: Me = await meResponse.json();
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Physical Asset Intelligence OS</h1>
        <a href="/api/auth/logout">Se déconnecter</a>
      </header>
      <p>
        Connecté en tant que <strong>{me.sub}</strong> — rôles : {me.roles.join(", ")}
      </p>

      <h2>Positions fonctionnelles</h2>
      {locations.length === 0 ? (
        <p>Aucune position fonctionnelle enregistrée pour l&apos;instant.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>Code</th>
              <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>Nom</th>
            </tr>
          </thead>
          <tbody>
            {locations.map((location) => (
              <tr key={location.id}>
                <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                  {location.code}
                </td>
                <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                  {location.name}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
