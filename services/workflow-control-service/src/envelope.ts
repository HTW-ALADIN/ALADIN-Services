import { collectResults, runControl } from "./control.js";
import { assertExactKeys, ControlError, isRecord } from "./errors.js";

export type Mode = "control" | "collect";

/** Evaluates one runner input envelope for the requested image mode. */
export function runEnvelope(mode: Mode, envelope: unknown): unknown {
  if (!isRecord(envelope)) {
    throw new ControlError("INVALID_ENVELOPE", "Input must be an object");
  }
  if (mode === "control") {
    assertExactKeys(
      envelope,
      ["params", "data"],
      "INVALID_ENVELOPE",
      "Control input accepts only params and data",
    );
    return runControl(envelope.params, envelope.data);
  }
  assertExactKeys(
    envelope,
    ["params", "joined"],
    "INVALID_ENVELOPE",
    "Collect input accepts only params and joined",
  );
  return collectResults(envelope.params, envelope.joined);
}