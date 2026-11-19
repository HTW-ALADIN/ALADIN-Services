import { ControlError, isRecord } from "./errors.js";
import { evaluateExpression } from "./expression.js";
import { readJsonPath } from "./jsonpath.js";
import type {
  InstructionSpec,
  JsonObject,
  JsonValue,
  JoinedState,
  StackOperations,
} from "./types.js";

export const MAX_CASES = 256;
export const MAX_ITEMS = 1_000;
export const MAX_PUSH_INSTRUCTIONS = 1_000;
export const MAX_DATA_BYTES = 1_048_576;

const BLOCK_PATTERN = /^[A-Za-z0-9._:/-]{1,200}$/;
const NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const OUTPUT_PATTERN = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;

interface BranchParams {
  kind: "branch";
  cases: { when: unknown; block: string }[];
  elseBlock?: string;
}

interface ForEachParams {
  kind: "forEach";
  over: string;
  as: string;
  concurrency: number;
  bodyBlock: string;
}

interface CollectParams {
  kind: "collect";
  order: string[];
  output?: string;
}

type ParsedControl = BranchParams | ForEachParams | CollectParams;

/** Evaluates a control step into runner-applied stack operations. */
export function runControl(params: unknown, data: unknown): StackOperations {
  if (!isRecord(data)) {
    throw new ControlError("INVALID_INPUT", "Task data must be an object");
  }
  assertDataSize(data);
  const payload = data as JsonObject;
  const control = parseControlParams(params);
  if (control.kind === "branch") return runBranch(control, payload);
  if (control.kind === "forEach") return runForEach(control, payload);
  throw new ControlError(
    "INVALID_MODE",
    "collect is a data step and cannot return stack operations",
  );
}

/** Collects ordered child results into the workflow output array. */
export function collectResults(params: unknown, joined: unknown): JsonValue[] {
  const control = parseControlParams(params);
  if (control.kind !== "collect") {
    throw new ControlError(
      "INVALID_MODE",
      "Only collect params can read joined results",
    );
  }
  const state = parseJoined(joined);
  return control.order.map((slot) => {
    if (!Object.hasOwn(state.slots, slot)) {
      throw new ControlError(
        "MISSING_SLOT",
        "Joined results do not contain every requested slot",
      );
    }
    const child = state.slots[slot];
    if (!isRecord(child)) {
      throw new ControlError("INVALID_JOINED", "Joined child is invalid");
    }
    if (child.error !== undefined) {
      throw new ControlError(
        "CHILD_FAILED",
        "A joined child failed before collection",
      );
    }
    if (!Object.hasOwn(child, "payload")) {
      throw new ControlError("INVALID_JOINED", "Joined child has no payload");
    }
    return selectChildOutput(child.payload, control.output);
  });
}

function parseControlParams(params: unknown): ParsedControl {
  if (!isRecord(params)) {
    throw new ControlError("INVALID_PARAMS", "Control params must be an object");
  }
  switch (params.kind) {
    case "branch":
      return parseBranch(params);
    case "forEach":
      return parseForEach(params);
    case "collect":
      return parseCollect(params);
    default:
      throw new ControlError("INVALID_PARAMS", "Control kind is invalid");
  }
}

function parseBranch(params: Record<string, unknown>): BranchParams {
  assertKeys(params, ["kind", "cases", "elseBlock"]);
  if (!Array.isArray(params.cases) || params.cases.length > MAX_CASES) {
    throw new ControlError(
      "INVALID_PARAMS",
      "Branch cases must be a bounded array",
    );
  }
  const cases = params.cases.map((entry) => {
    if (!isRecord(entry)) {
      throw new ControlError("INVALID_PARAMS", "Branch case must be an object");
    }
    assertKeys(entry, ["when", "block"]);
    if (!Object.hasOwn(entry, "when")) {
      throw new ControlError("INVALID_PARAMS", "Branch case requires a condition");
    }
    const block = readBlock(entry.block);
    return { when: entry.when, block };
  });
  const elseBlock =
    params.elseBlock === undefined ? undefined : readBlock(params.elseBlock);
  return { kind: "branch", cases, elseBlock };
}

function parseForEach(params: Record<string, unknown>): ForEachParams {
  assertKeys(params, ["kind", "over", "as", "concurrency", "bodyBlock"]);
  if (typeof params.over !== "string" || params.over.length === 0) {
    throw new ControlError("INVALID_PARAMS", "forEach over must be a path");
  }
  if (
    typeof params.as !== "string" ||
    !NAME_PATTERN.test(params.as)
  ) {
    throw new ControlError("INVALID_PARAMS", "forEach binding name is invalid");
  }
  if (
    typeof params.concurrency !== "number" ||
    !Number.isSafeInteger(params.concurrency) ||
    params.concurrency < 1 ||
    params.concurrency > MAX_ITEMS
  ) {
    throw new ControlError(
      "INVALID_PARAMS",
      "forEach concurrency must be a bounded positive integer",
    );
  }
  return {
    kind: "forEach",
    over: params.over,
    as: params.as,
    concurrency: params.concurrency,
    bodyBlock: readBlock(params.bodyBlock),
  };
}

function parseCollect(params: Record<string, unknown>): CollectParams {
  assertKeys(params, ["kind", "order", "output"]);
  if (!Array.isArray(params.order) || params.order.length > MAX_ITEMS) {
    throw new ControlError(
      "INVALID_PARAMS",
      "collect order must be a bounded array",
    );
  }
  const order: string[] = [];
  for (const slot of params.order) {
    if (typeof slot !== "string" || slot.length === 0) {
      throw new ControlError("INVALID_PARAMS", "collect slot is invalid");
    }
    if (order.includes(slot)) {
      throw new ControlError("INVALID_PARAMS", "collect slots must be unique");
    }
    order.push(slot);
  }
  if (
    params.output !== undefined &&
    (typeof params.output !== "string" ||
      !OUTPUT_PATTERN.test(params.output))
  ) {
    throw new ControlError("INVALID_PARAMS", "collect output name is invalid");
  }
  return {
    kind: "collect",
    order,
    ...(params.output === undefined ? {} : { output: params.output }),
  };
}

function runBranch(params: BranchParams, data: JsonObject): StackOperations {
  for (const controlCase of params.cases) {
    if (Boolean(evaluateExpression(controlCase.when, data))) {
      return { push: [{ op: "call", block: controlCase.block }] };
    }
  }
  return params.elseBlock === undefined
    ? {}
    : { push: [{ op: "call", block: params.elseBlock }] };
}

function runForEach(params: ForEachParams, data: JsonObject): StackOperations {
  const items = readJsonPath(data, params.over);
  if (items === undefined) {
    throw new ControlError(
      "INVALID_INPUT",
      "forEach path does not resolve to an array",
    );
  }
  if (!Array.isArray(items)) {
    throw new ControlError(
      "INVALID_INPUT",
      "forEach path must resolve to an array",
    );
  }
  if (items.length > MAX_ITEMS) {
    throw new ControlError("FAN_OUT_LIMIT", "forEach input is too large");
  }
  if (items.length === 0) return {};
  const spawns: InstructionSpec[] = items.map((element, index) => ({
    op: "spawn",
    block: params.bodyBlock,
    slot: String(index),
    input: {
      type: "value",
      payload: { ...data, [params.as]: element as JsonValue },
    },
  }));
  if (spawns.length + 1 > MAX_PUSH_INSTRUCTIONS) {
    throw new ControlError("FAN_OUT_LIMIT", "forEach pushes too many steps");
  }
  return {
    push: [{ op: "join" }, ...spawns],
  };
}

function parseJoined(joined: unknown): JoinedState {
  if (!isRecord(joined) || !isRecord(joined.slots)) {
    throw new ControlError("INVALID_JOINED", "Joined results are invalid");
  }
  return { slots: joined.slots as unknown as JoinedState["slots"] };
}

function selectChildOutput(payload: unknown, output: string | undefined): JsonValue {
  if (typeof payload === "string") {
    throw new ControlError(
      "UNRESOLVED_JOINED_PAYLOAD",
      "Joined payload is a data reference; the runtime must materialize it",
    );
  }
  if (output !== undefined) {
    if (!isRecord(payload) || !Object.hasOwn(payload, output)) {
      throw new ControlError(
        "MISSING_OUTPUT",
        "Joined child does not contain the requested output",
      );
    }
    return payload[output] as JsonValue;
  }
  if (isRecord(payload)) {
    const keys = Object.keys(payload);
    if (keys.length !== 1) {
      throw new ControlError(
        "AMBIGUOUS_OUTPUT",
        "Joined child has multiple outputs; specify an output name",
      );
    }
    return payload[keys[0] as string] as JsonValue;
  }
  return payload as JsonValue;
}

function readBlock(value: unknown): string {
  if (typeof value !== "string" || !BLOCK_PATTERN.test(value)) {
    throw new ControlError("INVALID_PARAMS", "Control block name is invalid");
  }
  return value;
}

function assertKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      throw new ControlError("INVALID_PARAMS", "Control params have an unknown field");
    }
  }
}

function assertDataSize(data: Record<string, unknown>): void {
  let serialized: string;
  try {
    serialized = JSON.stringify(data);
  } catch {
    throw new ControlError("INVALID_INPUT", "Task data is not valid JSON");
  }
  if (Buffer.byteLength(serialized, "utf8") > MAX_DATA_BYTES) {
    throw new ControlError("INPUT_LIMIT", "Task data exceeds the size limit");
  }
}