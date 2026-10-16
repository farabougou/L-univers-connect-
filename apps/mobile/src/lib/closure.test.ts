import { describe, expect, it } from "vitest";

import { CLOSURE_CODES, EMPTY_CLOSURE, type ClosureDraft, toClosureBody, validateClosure } from "./closure";

const complete: ClosureDraft = {
  ...EMPTY_CLOSURE,
  symptom_code: "no_heating",
  cause_code: "component_failure",
  action_code: "repair",
  verification_result: "ok",
  labor_minutes: "45",
};

describe("validateClosure", () => {
  it("accepte une clôture complète", () => {
    expect(validateClosure(complete)).toBeNull();
  });

  it.each([
    [{ symptom_code: null }, "incomplete"],
    [{ labor_minutes: "" }, "incomplete"],
    [{ labor_minutes: "1,5" }, "labor_invalid"],
    [{ labor_minutes: "-3" }, "labor_invalid"],
    [{ labor_minutes: "20000" }, "labor_invalid"],
    [{ action_code: "replacement" }, "replacement_requires_parts"],
    [{ parts: [{ reference: "", quantity: "1" }] }, "part_invalid"],
    [{ parts: [{ reference: "VANNE-3V", quantity: "0" }] }, "part_invalid"],
  ])("refuse %j (mêmes règles que l'API)", (change, key) => {
    expect(validateClosure({ ...complete, ...change })).toBe(`mobile.intervention.closure.${key}`);
  });
});

describe("toClosureBody", () => {
  it("convertit la saisie (virgule décimale comprise) sans note vide", () => {
    const body = toClosureBody({
      ...complete,
      action_code: "replacement",
      parts: [{ reference: " VANNE-3V-DN25 ", quantity: "1,5" }],
      note: "  ",
    });
    expect(body).toEqual({
      symptom_code: "no_heating",
      cause_code: "component_failure",
      action_code: "replacement",
      verification_result: "ok",
      labor_minutes: 45,
      parts: [{ reference: "VANNE-3V-DN25", quantity: 1.5 }],
    });
  });
});

it("les codes proposés viennent du catalogue partagé avec l'API", () => {
  expect(CLOSURE_CODES.symptoms).toContain("refrigerant_leak");
  expect(CLOSURE_CODES.verification_results).toEqual(["ok", "partial", "failed"]);
});
