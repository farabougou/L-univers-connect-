import { describe, expect, it } from "vitest";

import { summarizeSignals } from "./signals";

function signal(severity: string, ack = "acknowledged", handling = "open") {
  return { severity, ack_state: ack, handling_status: handling };
}

describe("summarizeSignals", () => {
  it("renvoie des zéros quand rien n'est ouvert", () => {
    expect(summarizeSignals([], [])).toEqual({
      alarmSeverity: { critical: 0, major: 0, warning: 0, info: 0 },
      findingSeverity: { critical: 0, major: 0, warning: 0, info: 0 },
      awaitingAck: 0,
      inProgress: 0,
    });
  });

  it("compte les alarmes et les constats séparément, par gravité", () => {
    const summary = summarizeSignals(
      [signal("critical"), signal("critical"), signal("major")],
      [signal("warning"), signal("info")],
    );

    expect(summary.alarmSeverity).toEqual({ critical: 2, major: 1, warning: 0, info: 0 });
    expect(summary.findingSeverity).toEqual({ critical: 0, major: 0, warning: 1, info: 1 });
  });

  it("compte ensemble les signaux à acquitter, alarmes et constats confondus", () => {
    const summary = summarizeSignals(
      [signal("critical", "unacknowledged"), signal("major", "acknowledged")],
      [signal("warning", "unacknowledged")],
    );

    expect(summary.awaitingAck).toBe(2);
  });

  it("compte ensemble les signaux en cours de traitement", () => {
    const summary = summarizeSignals(
      [signal("critical", "acknowledged", "in_progress")],
      [signal("warning", "acknowledged", "in_progress"), signal("info", "acknowledged", "open")],
    );

    expect(summary.inProgress).toBe(2);
  });

  it("ignore une gravité inconnue plutôt que de l'inventer", () => {
    const summary = summarizeSignals([signal("mystère")], []);

    expect(summary.alarmSeverity).toEqual({ critical: 0, major: 0, warning: 0, info: 0 });
  });
});
