import { describe, expect, it } from "vitest";

import { parseTagCode } from "./tagLookup";

describe("parseTagCode", () => {
  it("accepte un code tapé à la main", () => {
    expect(parseTagCode("AbC123xyZ")).toBe("AbC123xyZ");
  });

  it("retire le préfixe d'un QR scanné", () => {
    expect(parseTagCode("paios:tag:AbC123xyZ")).toBe("AbC123xyZ");
  });

  it("ignore les espaces autour du code", () => {
    expect(parseTagCode("  AbC123xyZ  ")).toBe("AbC123xyZ");
  });

  it("rejette un code trop court", () => {
    expect(parseTagCode("short")).toBeNull();
  });

  it("rejette un caractère hors alphabet", () => {
    expect(parseTagCode("AbC123xy!")).toBeNull();
  });

  it("rejette un QR d'une autre application", () => {
    expect(parseTagCode("https://example.com/other")).toBeNull();
  });
});
