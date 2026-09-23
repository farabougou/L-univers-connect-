import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchPassportByTag, isPlatformTag, parseTagCode, statusMessage } from "./passport";

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

describe("statusMessage", () => {
  const base = { reason: null, as_of: "2026-09-24T08:00:00Z" };

  it("n'affirme un état actuel qu'avec une communication en ligne", () => {
    expect(
      statusMessage({
        ...base,
        operational_status: "running",
        communication_status: "online",
        current: true,
      }).key,
    ).toBe("mobile.passport.status_current");
  });

  it("hors ligne : dernier état connu et sa date", () => {
    expect(
      statusMessage({
        ...base,
        operational_status: "running",
        communication_status: "offline",
        current: false,
      }),
    ).toEqual({
      key: "mobile.passport.status_offline",
      params: { state: "operational_status.running", since: "2026-09-24T08:00:00Z" },
    });
  });

  it("actualité invérifiable : le dit explicitement", () => {
    expect(
      statusMessage({
        ...base,
        operational_status: "disabled",
        communication_status: "unknown",
        current: false,
      }).key,
    ).toBe("mobile.passport.status_unverified");
  });

  it("sans point d'état ni donnée : état non disponible", () => {
    const unknown = { operational_status: "unknown", communication_status: "unknown", current: false };
    expect(statusMessage({ ...unknown, reason: "no_status_point", as_of: null }).key).toBe(
      "mobile.passport.status_no_point",
    );
    expect(statusMessage({ ...unknown, reason: "no_measurement", as_of: null }).key).toBe(
      "mobile.passport.status_no_measurement",
    );
  });
});

describe("isPlatformTag", () => {
  it("reconnaît une étiquette de la plateforme lue par l'appareil photo", () => {
    expect(isPlatformTag("paios:tag:Ab3_x-9Zk2LmN0pQ")).toBe(true);
  });

  it.each(["https://exemple.test/produit", "Ab3_x-9Zk2LmN0pQ", "paios:tag:", "WIFI:S:reseau;;"])(
    "refuse un QR étranger à la plateforme : %s",
    (scanned) => {
      expect(isPlatformTag(scanned)).toBe(false);
    },
  );
});
