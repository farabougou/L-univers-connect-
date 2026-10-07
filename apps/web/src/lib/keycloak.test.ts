import { describe, expect, it } from "vitest";

import { keycloakAdminConsoleUrl } from "./keycloak";

describe("keycloakAdminConsoleUrl", () => {
  it("dérive la console d'administration depuis l'adresse OIDC standard", () => {
    expect(
      keycloakAdminConsoleUrl("https://auth.exemple.com/realms/paios"),
    ).toBe("https://auth.exemple.com/admin/master/console/#/paios/users");
  });

  it("gère une barre oblique finale sur le realm", () => {
    expect(
      keycloakAdminConsoleUrl("https://auth.exemple.com/realms/paios/"),
    ).toBe("https://auth.exemple.com/admin/master/console/#/paios/users");
  });

  it("renvoie null si l'adresse ne suit pas le format attendu", () => {
    expect(
      keycloakAdminConsoleUrl("https://auth.exemple.com/autre-chose"),
    ).toBeNull();
  });
});
