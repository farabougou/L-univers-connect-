import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import { generatePkcePair, generateState } from "./pkce";

// RFC 7636 : le "code verifier" doit être composé uniquement de caractères
// non réservés, longueur entre 43 et 128.
const UNRESERVED_CHARS = /^[A-Za-z0-9\-._~]+$/;

describe("generatePkcePair", () => {
  it("génère un code_verifier conforme à RFC 7636 (longueur et alphabet)", () => {
    const { codeVerifier } = generatePkcePair();
    expect(codeVerifier.length).toBeGreaterThanOrEqual(43);
    expect(codeVerifier.length).toBeLessThanOrEqual(128);
    expect(codeVerifier).toMatch(UNRESERVED_CHARS);
  });

  it("dérive le code_challenge par SHA-256 + base64url (méthode S256)", () => {
    const { codeVerifier, codeChallenge } = generatePkcePair();
    const expected = createHash("sha256").update(codeVerifier).digest("base64url");
    expect(codeChallenge).toBe(expected);
  });

  it("génère une paire différente à chaque appel", () => {
    const first = generatePkcePair();
    const second = generatePkcePair();
    expect(first.codeVerifier).not.toBe(second.codeVerifier);
  });
});

describe("generateState", () => {
  it("génère une valeur non vide et différente à chaque appel", () => {
    const first = generateState();
    const second = generateState();
    expect(first.length).toBeGreaterThan(0);
    expect(first).not.toBe(second);
  });
});
