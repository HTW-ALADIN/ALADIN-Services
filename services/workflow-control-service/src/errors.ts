/** Safe, bounded control-flow failure. Messages never echo input values. */
export class ControlError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly retryable = false,
  ) {
    super(message);
    this.name = "ControlError";
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function requireRecord(
  value: unknown,
  code: string,
  message: string,
): Record<string, unknown> {
  if (!isRecord(value)) throw new ControlError(code, message);
  return value;
}

export function assertExactKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
  code: string,
  message: string,
): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) throw new ControlError(code, message);
  }
}