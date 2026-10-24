import { NextResponse } from "next/server";

/**
 * Point de contrôle pour Railway (et tout autre supervisseur) : ne doit
 * dépendre ni de Keycloak, ni de l'API, ni d'un rendu de page (`/login`
 * fait un rendu dynamique complet avec traduction — trop fragile pour
 * servir de vérification de santé).
 */
export async function GET() {
  return NextResponse.json({ status: "ok" });
}
