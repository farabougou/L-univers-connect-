import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch, requireAccessToken, redirect } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  requireAccessToken: vi.fn(),
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
}));

vi.mock("@/lib/api", () => ({ apiFetch, requireAccessToken }));
vi.mock("next/navigation", () => ({ redirect }));

import { lookupTag } from "./actions";

function fd(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.set(key, value);
  return data;
}

function ok(body: unknown): Response {
  return { ok: true, json: async () => body } as Response;
}

function fail(code: string): Response {
  return { ok: false, json: async () => ({ code }) } as Response;
}

async function redirected(action: Promise<unknown>): Promise<string> {
  try {
    await action;
    throw new Error("l'action aurait dû rediriger");
  } catch (error) {
    return (error as Error).message.replace("REDIRECT:", "");
  }
}

beforeEach(() => {
  vi.clearAllMocks();
  requireAccessToken.mockResolvedValue("token-123");
});

describe("lookupTag", () => {
  it("résout un code tapé à la main et mène à la fiche équipement", async () => {
    apiFetch.mockResolvedValueOnce(ok({ tag: { node_id: "node-1" }, passport: {} }));
    const url = await redirected(lookupTag(fd({ code: "AbC123xyZ" })));

    expect(apiFetch).toHaveBeenCalledWith("/tags/AbC123xyZ", "token-123");
    expect(url).toBe("/registre/node-1");
  });

  it("accepte un code préfixé comme un QR scanné", async () => {
    apiFetch.mockResolvedValueOnce(ok({ tag: { node_id: "node-2" }, passport: {} }));
    const url = await redirected(lookupTag(fd({ code: "paios:tag:AbC123xyZ" })));

    expect(apiFetch).toHaveBeenCalledWith("/tags/AbC123xyZ", "token-123");
    expect(url).toBe("/registre/node-2");
  });

  it("redirige avec une erreur de forme sans appeler l'API pour un code invalide", async () => {
    const url = await redirected(lookupTag(fd({ code: "trop court" })));

    expect(apiFetch).not.toHaveBeenCalled();
    expect(url).toBe("/passeport?error=TAG_INVALID_CODE");
  });

  it("redirige avec le code d'erreur du serveur pour une étiquette inconnue", async () => {
    apiFetch.mockResolvedValueOnce(fail("TAG_UNKNOWN"));
    const url = await redirected(lookupTag(fd({ code: "AbC123xyZ" })));

    expect(url).toBe("/passeport?error=TAG_UNKNOWN");
  });

  it("redirige avec le code d'erreur du serveur pour une étiquette révoquée", async () => {
    apiFetch.mockResolvedValueOnce(fail("TAG_REVOKED"));
    const url = await redirected(lookupTag(fd({ code: "AbC123xyZ" })));

    expect(url).toBe("/passeport?error=TAG_REVOKED");
  });
});
