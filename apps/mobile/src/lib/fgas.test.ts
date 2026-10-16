import { describe, expect, it } from "vitest";

import { FGAS_CODES, emptyFgas, toFgasBody, validateFgas } from "./fgas";

const complete = {
  ...emptyFgas(),
  operator_name: "Froid Services SARL",
  detenteur_name: "Client Demo",
  equipment_identification: "PAC-01 — Chaufferie",
  refrigerant_name: "R410A",
  total_charge_kg: "12,5",
  nature_of_intervention: ["maintenance"],
  operator_signatory_name: "Mohamed",
  signed_at: "2026-10-02",
};

describe("validateFgas", () => {
  it("accepte une fiche complète", () => {
    expect(validateFgas(complete)).toBeNull();
  });

  it.each([
    [{ operator_name: "" }, "incomplete"],
    [{ detenteur_name: "" }, "incomplete"],
    [{ equipment_identification: "" }, "incomplete"],
    [{ refrigerant_name: "" }, "incomplete"],
    [{ operator_signatory_name: "" }, "incomplete"],
    [{ signed_at: "" }, "incomplete"],
    [{ total_charge_kg: "" }, "total_charge_invalid"],
    [{ total_charge_kg: "-1" }, "total_charge_invalid"],
    [{ nature_of_intervention: [] }, "nature_required"],
    [{ nature_of_intervention: ["other"] }, "nature_other_detail_required"],
    [
      { waste_classification: ["other_non_flammable"] },
      "waste_other_detail_required",
    ],
    [
      { waste_classification: ["other_flammable"] },
      "waste_other_detail_required",
    ],
    [{ leaks: [{ location: "", repaired: null }] }, "leak_location_required"],
    [{ charged_virgin_kg: "-1" }, "quantity_invalid"],
    [{ co2_equivalent_tonnes: "-1" }, "quantity_invalid"],
  ])("refuse %j (mêmes règles que l'API)", (change, key) => {
    expect(validateFgas({ ...complete, ...change })).toBe(`mobile.intervention.fgas.${key}`);
  });
});

describe("toFgasBody", () => {
  it("convertit la saisie (virgule décimale comprise) sans champ optionnel vide", () => {
    const body = toFgasBody({
      ...complete,
      total_charge_kg: "12,5",
      charged_virgin_kg: "1,5",
      operator_address: "  ",
      leaks: [{ location: " Vanne basse pression ", repaired: true }],
    });
    expect(body.total_charge_kg).toBe(12.5);
    expect(body.charged_virgin_kg).toBe(1.5);
    expect(body.operator_address).toBeNull();
    expect(body.leaks).toEqual([{ location: "Vanne basse pression", repaired: true }]);
    expect(body.co2_equivalent_tonnes).toBeNull();
  });
});

it("les codes proposés viennent du catalogue partagé avec l'API", () => {
  expect(FGAS_CODES.nature_of_intervention).toContain("leak_check_periodic");
  expect(FGAS_CODES.waste_classification).toEqual([
    "un1078_non_flammable",
    "other_non_flammable",
    "un3161_flammable",
    "other_flammable",
  ]);
});
