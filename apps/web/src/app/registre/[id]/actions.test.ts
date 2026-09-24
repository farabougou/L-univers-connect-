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
  acknowledgeSignal,
  activateRule,
  changeLifecycleState,
  clearAlarm,
  confirmFinding,
  createDivergenceRule,
  createThresholdRule,
  createWorkOrderForEquipment,
  declareDesiredState,
  endDesiredState,
  retireRule,
  revokeTag,
  setHandling,
  setProperty,
} from "./actions";

function fd(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.set(key, value);
  return data;
}

function ok(body: unknown = {}): Response {
  return { ok: true, json: async () => body } as Response;
}

function fail(code?: string): Response {
  return { ok: false, json: async () => (code ? { code } : null) } as Response;
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

describe("redirection en cas d'échec", () => {
  it("porte le code d'erreur de l'API dans l'URL", async () => {
    apiFetch.mockResolvedValueOnce(fail("SIGNAL_ALREADY_ACKNOWLEDGED"));
    const url = await redirected(
      acknowledgeSignal(fd({ kind: "alarm", signal_id: "sig-1", node_id: "node-1" })),
    );
    expect(url).toBe("/registre/node-1?error=SIGNAL_ALREADY_ACKNOWLEDGED");
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("retombe sur CREATION_FAILED quand l'API ne renvoie pas de code", async () => {
    apiFetch.mockResolvedValueOnce(fail());
    const url = await redirected(
      acknowledgeSignal(fd({ kind: "alarm", signal_id: "sig-1", node_id: "node-1" })),
    );
    expect(url).toBe("/registre/node-1?error=CREATION_FAILED");
  });
});

describe("basePath selon le type de signal", () => {
  it.each([
    ["alarm", "/alarms/sig-1/acknowledge"],
    ["finding", "/findings/sig-1/acknowledge"],
  ])("acknowledgeSignal(kind=%s) appelle %s", async (kind, path) => {
    apiFetch.mockResolvedValueOnce(ok());
    await acknowledgeSignal(fd({ kind, signal_id: "sig-1", node_id: "node-1" }));
    expect(apiFetch).toHaveBeenCalledWith(path, "token-123", expect.objectContaining({ method: "POST" }));
  });

  it.each([
    ["alarm", "/alarms/sig-1/handling"],
    ["finding", "/findings/sig-1/handling"],
  ])("setHandling(kind=%s) appelle %s en PATCH", async (kind, path) => {
    apiFetch.mockResolvedValueOnce(ok());
    await setHandling(fd({ kind, signal_id: "sig-1", node_id: "node-1", handling_status: "closed" }));
    expect(apiFetch).toHaveBeenCalledWith(
      path,
      "token-123",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ handling_status: "closed" }),
      }),
    );
  });
});

describe("confirmFinding", () => {
  it("envoie la note à /findings/{id}/confirm", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await confirmFinding(fd({ signal_id: "find-1", node_id: "node-1", note: "Vérifié sur site" }));
    expect(apiFetch).toHaveBeenCalledWith(
      "/findings/find-1/confirm",
      "token-123",
      expect.objectContaining({ body: JSON.stringify({ note: "Vérifié sur site" }) }),
    );
    expect(revalidatePath).toHaveBeenCalledWith("/registre/node-1");
  });
});

describe("clearAlarm", () => {
  it("appelle /alarms/{id}/clear", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await clearAlarm(fd({ signal_id: "alarm-1", node_id: "node-1" }));
    expect(apiFetch).toHaveBeenCalledWith(
      "/alarms/alarm-1/clear",
      "token-123",
      expect.objectContaining({ method: "POST", body: JSON.stringify({}) }),
    );
  });
});

describe("createThresholdRule", () => {
  const base = {
    node_id: "node-1",
    point_id: "point-1",
    reason: "Nouvelle règle",
    severity: "critical",
    title: "Température haute",
    operator: ">",
    threshold: "80",
  };

  it("construit le contenu threshold avec create_work_order=false par défaut et recommended_action=null", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await createThresholdRule(fd(base));

    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body).toEqual({
      config_type: "alarm_rule",
      subject_key: "point-1",
      reason: "Nouvelle règle",
      content: {
        kind: "threshold",
        point_id: "point-1",
        severity: "critical",
        title: "Température haute",
        recommended_action: null,
        create_work_order: false,
        operator: ">",
        threshold: 80,
      },
    });
  });

  it("passe create_work_order=true et transmet recommended_action quand fournis", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await createThresholdRule(
      fd({ ...base, create_work_order: "on", recommended_action: "Contrôler le compresseur" }),
    );

    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body.content.create_work_order).toBe(true);
    expect(body.content.recommended_action).toBe("Contrôler le compresseur");
  });
});

describe("createDivergenceRule", () => {
  it("construit le contenu desired_state_divergence avec tolerance numérique", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await createDivergenceRule(
      fd({
        node_id: "node-1",
        point_id: "point-1",
        reason: "Écart",
        severity: "warning",
        title: "Écart de consigne",
        tolerance: "2.5",
      }),
    );

    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body.content).toEqual({
      kind: "desired_state_divergence",
      point_id: "point-1",
      severity: "warning",
      title: "Écart de consigne",
      recommended_action: null,
      create_work_order: false,
      tolerance: 2.5,
    });
  });
});

describe("activateRule / retireRule", () => {
  it("activateRule appelle /configs/{id}/activate sans corps", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await activateRule(fd({ node_id: "node-1", version_id: "ver-1" }));
    expect(apiFetch).toHaveBeenCalledWith("/configs/ver-1/activate", "token-123", { method: "POST" });
  });

  it("retireRule transmet la raison", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await retireRule(fd({ node_id: "node-1", version_id: "ver-1", reason: "Obsolète" }));
    expect(apiFetch).toHaveBeenCalledWith(
      "/configs/ver-1/retire",
      "token-123",
      expect.objectContaining({ body: JSON.stringify({ reason: "Obsolète" }) }),
    );
  });
});

describe("declareDesiredState", () => {
  it("convertit value en nombre et les champs optionnels absents en null", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await declareDesiredState(
      fd({ node_id: "node-1", point_id: "point-1", value: "21.5", reason: "Consigne hiver" }),
    );

    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body).toEqual({
      value: 21.5,
      reason: "Consigne hiver",
      daily_start: null,
      daily_end: null,
      timezone: null,
    });
  });

  it("transmet la plage horaire et le fuseau quand fournis", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await declareDesiredState(
      fd({
        node_id: "node-1",
        point_id: "point-1",
        value: "21.5",
        reason: "Consigne hiver",
        daily_start: "06:00",
        daily_end: "20:00",
        timezone: "Africa/Bamako",
      }),
    );

    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body.daily_start).toBe("06:00");
    expect(body.daily_end).toBe("20:00");
    expect(body.timezone).toBe("Africa/Bamako");
  });
});

describe("endDesiredState", () => {
  it("appelle /desired-states/{id}/end", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await endDesiredState(fd({ node_id: "node-1", desired_state_id: "ds-1" }));
    expect(apiFetch).toHaveBeenCalledWith(
      "/desired-states/ds-1/end",
      "token-123",
      expect.objectContaining({ body: JSON.stringify({}) }),
    );
  });
});

describe("changeLifecycleState", () => {
  it("note absente devient null", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await changeLifecycleState(fd({ node_id: "node-1", physical_unit_id: "unit-1", to_state: "installed" }));
    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body).toEqual({ to_state: "installed", note: null });
  });
});

describe("setProperty", () => {
  it("convertit une valeur numérique en nombre", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await setProperty(
      fd({
        node_id: "node-1",
        unit_id: "unit-1",
        key: "manufacture_year",
        value: "2019",
        source: "manufacturer_plate",
        reason: "Relevé plaque",
      }),
    );
    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body.value).toBe(2019);
    expect(typeof body.value).toBe("number");
  });

  it("garde une valeur non numérique en texte (ex. type de fluide)", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await setProperty(
      fd({
        node_id: "node-1",
        unit_id: "unit-1",
        key: "refrigerant_type",
        value: "R32",
        source: "manufacturer_plate",
        reason: "Relevé plaque",
      }),
    );
    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body.value).toBe("R32");
    expect(typeof body.value).toBe("string");
  });

  it("unit absente devient null", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await setProperty(
      fd({
        node_id: "node-1",
        unit_id: "unit-1",
        key: "refrigerant_type",
        value: "R32",
        source: "manufacturer_plate",
        reason: "Relevé plaque",
      }),
    );
    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body.unit).toBeNull();
  });
});

describe("revokeTag", () => {
  it("appelle /tags/{code}/revoke avec la raison", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await revokeTag(fd({ node_id: "node-1", code: "TAG-1", reason: "Perdue" }));
    expect(apiFetch).toHaveBeenCalledWith(
      "/tags/TAG-1/revoke",
      "token-123",
      expect.objectContaining({ body: JSON.stringify({ reason: "Perdue" }) }),
    );
  });
});

describe("createWorkOrderForEquipment", () => {
  it("utilise node_id comme functional_location_id", async () => {
    apiFetch.mockResolvedValueOnce(ok());
    await createWorkOrderForEquipment(
      fd({ node_id: "node-1", title: "Vérifier fuite", work_order_type: "corrective", priority: "high" }),
    );
    const body = JSON.parse(apiFetch.mock.calls[0][2].body);
    expect(body).toEqual({
      title: "Vérifier fuite",
      work_order_type: "corrective",
      priority: "high",
      functional_location_id: "node-1",
    });
  });
});
