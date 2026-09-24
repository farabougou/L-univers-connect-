import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch, requireAccessToken, redirect, revalidatePath } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  requireAccessToken: vi.fn(),
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
  revalidatePath: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ apiFetch, requireAccessToken }));
vi.mock("next/navigation", () => ({ redirect }));
vi.mock("next/cache", () => ({ revalidatePath }));

import {
  closeSpace,
  createEquipment,
  createSite,
  createSpace,
  showTag,
  updateSiteTimezone,
} from "./actions";

function fd(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.set(key, value);
  return data;
}

function ok(body: unknown = {}): Response {
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

describe("createSite", () => {
  it("crée le site puis revalide la page", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await createSite(fd({ name: "Site A", timezone: "Africa/Bamako" }));

    expect(apiFetch).toHaveBeenCalledWith("/sites", "token-123", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Site A", timezone: "Africa/Bamako" }),
    });
    expect(revalidatePath).toHaveBeenCalledWith("/registre");
  });

  it("redirige avec le code d'erreur en cas d'échec", async () => {
    apiFetch.mockResolvedValueOnce(fail("SITE_NAME_TAKEN"));
    const url = await redirected(createSite(fd({ name: "Site A", timezone: "Africa/Bamako" })));

    expect(url).toBe("/registre?error=SITE_NAME_TAKEN");
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});

describe("createSpace", () => {
  it("envoie parent_id à null quand aucun parent n'est choisi", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await createSpace(fd({ site_id: "site-1", space_type: "room", code: "R1", name: "Salle 1" }));

    expect(apiFetch).toHaveBeenCalledWith("/spaces", "token-123", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        site_id: "site-1",
        parent_id: null,
        space_type: "room",
        code: "R1",
        name: "Salle 1",
      }),
    });
  });

  it("transmet parent_id quand un parent est choisi", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await createSpace(
      fd({
        site_id: "site-1",
        parent_id: "space-parent",
        space_type: "room",
        code: "R1",
        name: "Salle 1",
      }),
    );

    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body.parent_id).toBe("space-parent");
  });
});

describe("closeSpace", () => {
  it("appelle /spaces/{id}/close avec la raison", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await closeSpace(fd({ space_id: "space-1", reason: "Démolition" }));

    expect(apiFetch).toHaveBeenCalledWith("/spaces/space-1/close", "token-123", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Démolition" }),
    });
  });
});

describe("updateSiteTimezone", () => {
  it("appelle /sites/{id}/timezone en PUT", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await updateSiteTimezone(fd({ site_id: "site-1", timezone: "Europe/Paris" }));

    expect(apiFetch).toHaveBeenCalledWith("/sites/site-1/timezone", "token-123", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timezone: "Europe/Paris" }),
    });
  });
});

describe("createEquipment", () => {
  const fields = {
    site_id: "site-1",
    space_id: "space-1",
    code: "EQ-1",
    name: "PAC toiture",
    equipment_type: "heat_pump",
    manufacturer: "Daikin",
    reference: "ABC123",
    serial_number: "SN-1",
  };

  it("enchaîne modèle, exemplaire, emplacement, affectation et étiquette, puis redirige avec le QR", async () => {
    apiFetch
      .mockResolvedValueOnce(ok({ id: "model-1" })) // product-models
      .mockResolvedValueOnce(ok({ id: "unit-1" })) // physical-units
      .mockResolvedValueOnce(ok({ id: "loc-1", name: "PAC toiture" })) // functional-locations
      .mockResolvedValueOnce(ok({})) // assignment
      .mockResolvedValueOnce(ok({ payload: "TAG-XYZ" })); // tags

    const url = await redirected(createEquipment(fd(fields)));

    expect(apiFetch).toHaveBeenNthCalledWith(
      1,
      "/product-models",
      "token-123",
      expect.objectContaining({
        body: JSON.stringify({
          manufacturer: "Daikin",
          reference: "ABC123",
          equipment_type: "heat_pump",
        }),
      }),
    );
    expect(apiFetch).toHaveBeenNthCalledWith(
      2,
      "/physical-units",
      "token-123",
      expect.objectContaining({
        body: JSON.stringify({ product_model_id: "model-1", serial_number: "SN-1" }),
      }),
    );
    expect(apiFetch).toHaveBeenNthCalledWith(
      3,
      "/functional-locations",
      "token-123",
      expect.objectContaining({
        body: JSON.stringify({
          site_id: "site-1",
          code: "EQ-1",
          name: "PAC toiture",
          kind: "equipment",
          space_id: "space-1",
        }),
      }),
    );
    expect(apiFetch).toHaveBeenNthCalledWith(
      4,
      "/functional-locations/loc-1/assignment",
      "token-123",
      expect.objectContaining({ body: JSON.stringify({ physical_unit_id: "unit-1" }) }),
    );
    expect(apiFetch).toHaveBeenNthCalledWith(
      5,
      "/graph/nodes/loc-1/tags",
      "token-123",
      expect.objectContaining({ body: JSON.stringify({ tag_type: "qr" }) }),
    );
    expect(url).toBe("/registre?tag=TAG-XYZ&label=PAC%20toiture");
    expect(revalidatePath).toHaveBeenCalledWith("/registre");
  });

  it("s'arrête et redirige dès qu'une étape échoue, sans appeler les suivantes", async () => {
    apiFetch
      .mockResolvedValueOnce(ok({ id: "model-1" }))
      .mockResolvedValueOnce(fail("SERIAL_NUMBER_TAKEN"));

    const url = await redirected(createEquipment(fd(fields)));

    expect(url).toBe("/registre?error=SERIAL_NUMBER_TAKEN");
    expect(apiFetch).toHaveBeenCalledTimes(2);
  });

  it("space_id absent est transmis comme null", async () => {
    apiFetch
      .mockResolvedValueOnce(ok({ id: "model-1" }))
      .mockResolvedValueOnce(ok({ id: "unit-1" }))
      .mockResolvedValueOnce(fail("STOP"));

    const rest = { ...fields } as Record<string, string>;
    delete rest.space_id;
    await redirected(createEquipment(fd(rest)));

    const body = JSON.parse(apiFetch.mock.calls[2][2].body);
    expect(body.space_id).toBeNull();
  });
});

describe("showTag", () => {
  it("réutilise l'étiquette active existante sans en créer une nouvelle", async () => {
    apiFetch.mockResolvedValueOnce(
      ok([
        { status: "revoked", payload: "OLD" },
        { status: "active", payload: "TAG-ACTIVE" },
      ]),
    );

    const url = await redirected(
      showTag(fd({ functional_location_id: "loc-1", label: "PAC toiture" })),
    );

    expect(url).toBe("/registre?tag=TAG-ACTIVE&label=PAC%20toiture");
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  it("crée une étiquette quand aucune n'est active", async () => {
    apiFetch
      .mockResolvedValueOnce(ok([{ status: "revoked", payload: "OLD" }]))
      .mockResolvedValueOnce(ok({ payload: "TAG-NEW" }));

    const url = await redirected(
      showTag(fd({ functional_location_id: "loc-1", label: "PAC toiture" })),
    );

    expect(url).toBe("/registre?tag=TAG-NEW&label=PAC%20toiture");
    expect(apiFetch).toHaveBeenNthCalledWith(
      2,
      "/graph/nodes/loc-1/tags",
      "token-123",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ tag_type: "qr" }) }),
    );
  });

  it("redirige avec une erreur si la liste des étiquettes échoue", async () => {
    apiFetch.mockResolvedValueOnce(fail("NODE_NOT_FOUND"));
    const url = await redirected(
      showTag(fd({ functional_location_id: "loc-1", label: "PAC toiture" })),
    );
    expect(url).toBe("/registre?error=NODE_NOT_FOUND");
  });
});
