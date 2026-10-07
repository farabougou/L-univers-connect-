import { describe, expect, it } from "vitest";

import { isAccessTokenExpired, REFRESH_MARGIN_MS } from "./token-expiry";

describe("isAccessTokenExpired", () => {
  it("n'est pas expiré largement avant l'échéance", () => {
    const now = 1_000_000;
    const expiresAt = now + 60_000;
    expect(isAccessTokenExpired(expiresAt, now)).toBe(false);
  });

  it("est considéré expiré une fois dans la marge de sécurité", () => {
    const now = 1_000_000;
    const expiresAt = now + REFRESH_MARGIN_MS - 1;
    expect(isAccessTokenExpired(expiresAt, now)).toBe(true);
  });

  it("est expiré pile à l'échéance", () => {
    const now = 1_000_000;
    expect(isAccessTokenExpired(now, now)).toBe(true);
  });

  it("est expiré après l'échéance", () => {
    const now = 1_000_000;
    const expiresAt = now - 1;
    expect(isAccessTokenExpired(expiresAt, now)).toBe(true);
  });

  it("n'est pas expiré juste avant le début de la marge", () => {
    const now = 1_000_000;
    const expiresAt = now + REFRESH_MARGIN_MS + 1;
    expect(isAccessTokenExpired(expiresAt, now)).toBe(false);
  });
});
