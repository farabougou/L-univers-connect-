import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchPassportByTag, parseTagCode } from "./passport";

describe("parseTagCode", () => {
  it("accepte le contenu brut d'un QR", () => {
    expect(parseTagCode("paios:tag:Ab3_x-9Zk2LmN0pQ")).toBe("Ab3_x-9Zk2LmN0pQ");
  });

  it("accepte un code tapé à la main, espaces retirés", () => {
    expect(parseTagCode("  Ab3_x-9Zk2LmN0pQ \n")).toBe("Ab3_x-9Zk2LmN0pQ");
  });

  it.each(["", "paios:tag:", "abc", "https://exemple.test/x", "code avec espaces", "a/../b1234"])(
    "refuse ce qui n'est pas un code d'étiquette : %s",
    (input) => {
      expect(parseTagCode(input)).toBeNull();
    },
  );
});

describe("fetchPassportByTag", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch(status: number, body: unknown = {}) {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("renvoie le passeport et envoie le jeton", async () => {
    const passport = { node_id: "n1", node_type: "physical_unit", allowed_actions: [] };
    const fetchMock = stubFetch(200, { tag: {}, passport });

    const result = await fetchPassportByTag("https://api.test", "jeton", "Ab3_x-9Zk2LmN0pQ", "en");

    expect(result).toEqual({ ok: true, passport });
    expect(fetchMock).toHaveBeenCalledWith("https://api.test/tags/Ab3_x-9Zk2LmN0pQ", {
      headers: { Authorization: "Bearer jeton", "Accept-Language": "en" },
    });
  });

  it.each([
    [404, { ok: false, messageKey: "mobile.passport.tag_unknown" }],
    [410, { ok: false, messageKey: "mobile.passport.tag_revoked" }],
    [403, { ok: false, messageKey: "mobile.passport.forbidden" }],
    [500, { ok: false, messageKey: "mobile.passport.server_error", params: { status: 500 } }],
  ])("traduit le code %i en clé de message", async (status, expected) => {
    stubFetch(status);
    const result = await fetchPassportByTag("https://api.test", "jeton", "Ab3_x-9Zk2LmN0pQ", "fr");
    expect(result).toEqual(expected);
  });

  it("signale l'absence de réseau", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Network request failed")));
    const result = await fetchPassportByTag("https://api.test", "jeton", "Ab3_x-9Zk2LmN0pQ", "fr");
    expect(result).toEqual({ ok: false, messageKey: "mobile.passport.offline" });
  });
});
