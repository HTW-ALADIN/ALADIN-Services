import { ControlError, isRecord } from "./errors.js";
import { readJsonPath } from "./jsonpath.js";
import type { JsonObject, JsonValue } from "./types.js";

const MAX_DEPTH = 64;
const MAX_NODES = 1_000;
const MAX_LIST = 256;

interface Budget {
  nodes: number;
}

/**
 * Evaluates the bounded workflow expression subset against task data.
 * Only `data` and `literal` bindings are available in this image; request
 * parameters, item data, sessions and forEach elements must be materialized
 * into task data by the compiler/runtime if an expression needs them.
 */
export function evaluateExpression(
  expression: unknown,
  data: JsonObject,
): JsonValue {
  return evaluate(expression, data, { nodes: 0 }, 0);
}

function evaluate(
  expression: unknown,
  data: JsonObject,
  budget: Budget,
  depth: number,
): JsonValue {
  budget.nodes += 1;
  if (budget.nodes > MAX_NODES) {
    throw new ControlError(
      "EXPRESSION_TOO_LARGE",
      "Expression exceeds the evaluation budget",
    );
  }
  if (depth > MAX_DEPTH) {
    throw new ControlError(
      "EXPRESSION_TOO_DEEP",
      "Expression exceeds the nesting limit",
    );
  }
  if (!isRecord(expression)) {
    throw new ControlError("INVALID_EXPRESSION", "Expression must be an object");
  }

  if (typeof expression.op === "string") {
    return evaluateOperation(expression, data, budget, depth);
  }
  if (typeof expression.from === "string") {
    return evaluateBinding(expression, data);
  }
  throw new ControlError(
    "INVALID_EXPRESSION",
    "Expression must be an operation or binding",
  );
}

function evaluateBinding(
  expression: Record<string, unknown>,
  data: JsonObject,
): JsonValue {
  const from = expression.from;
  if (from === "literal") {
    assertKeys(expression, ["from", "value"]);
    if (!Object.hasOwn(expression, "value")) {
      throw new ControlError("INVALID_BINDING", "Literal binding has no value");
    }
    return expression.value as JsonValue;
  }
  if (from === "data") {
    assertKeys(expression, ["from", "path"]);
    if (typeof expression.path !== "string") {
      throw new ControlError("INVALID_BINDING", "Data binding requires a path");
    }
    return normalize(readJsonPath(data, expression.path));
  }
  if (
    from === "param" ||
    from === "item" ||
    from === "session" ||
    from === "element"
  ) {
    throw new ControlError(
      "UNSUPPORTED_BINDING",
      "Only data and literal bindings are available to control evaluation",
    );
  }
  throw new ControlError("INVALID_BINDING", "Binding source is invalid");
}

function evaluateOperation(
  expression: Record<string, unknown>,
  data: JsonObject,
  budget: Budget,
  depth: number,
): JsonValue {
  const op = expression.op;
  switch (op) {
    case "not": {
      assertKeys(expression, ["op", "value"]);
      return !truthy(
        evaluate(expression.value, data, budget, depth + 1),
      );
    }
    case "and":
    case "or": {
      assertKeys(expression, ["op", "values"]);
      const values = expression.values;
      if (!Array.isArray(values) || values.length > MAX_LIST) {
        throw new ControlError(
          "INVALID_EXPRESSION",
          "Logical operands must be a bounded array",
        );
      }
      if (values.length === 0) return op === "and";
      for (const value of values) {
        const result = truthy(evaluate(value, data, budget, depth + 1));
        if (op === "and" && !result) return false;
        if (op === "or" && result) return true;
      }
      return op === "and";
    }
    case "eq":
    case "ne": {
      assertKeys(expression, ["op", "left", "right"]);
      const equal = deepEqual(
        evaluate(expression.left, data, budget, depth + 1),
        evaluate(expression.right, data, budget, depth + 1),
      );
      return op === "eq" ? equal : !equal;
    }
    case "gt":
    case "gte":
    case "lt":
    case "lte": {
      assertKeys(expression, ["op", "left", "right"]);
      return compare(
        op,
        evaluate(expression.left, data, budget, depth + 1),
        evaluate(expression.right, data, budget, depth + 1),
      );
    }
    case "contains":
    case "in": {
      assertKeys(expression, ["op", "left", "right"]);
      const left = evaluate(expression.left, data, budget, depth + 1);
      const right = evaluate(expression.right, data, budget, depth + 1);
      return op === "contains" ? contains(left, right) : contains(right, left);
    }
    case "get": {
      assertKeys(expression, ["op", "from", "path"]);
      if (typeof expression.path !== "string") {
        throw new ControlError("INVALID_EXPRESSION", "get requires a path");
      }
      const from = evaluate(expression.from, data, budget, depth + 1);
      return normalize(readJsonPath(from, expression.path));
    }
    default:
      throw new ControlError("INVALID_EXPRESSION", "Expression op is invalid");
  }
}

function assertKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      throw new ControlError(
        "INVALID_EXPRESSION",
        "Expression has an unknown field",
      );
    }
  }
}

function normalize(value: unknown): JsonValue {
  return value === undefined ? null : (value as JsonValue);
}

function truthy(value: JsonValue): boolean {
  return Boolean(value);
}

function compare(
  op: "gt" | "gte" | "lt" | "lte",
  left: JsonValue,
  right: JsonValue,
): boolean {
  if (typeof left === "number" && typeof right === "number") {
    return op === "gt"
      ? left > right
      : op === "gte"
        ? left >= right
        : op === "lt"
          ? left < right
          : left <= right;
  }
  if (typeof left === "string" && typeof right === "string") {
    return op === "gt"
      ? left > right
      : op === "gte"
        ? left >= right
        : op === "lt"
          ? left < right
          : left <= right;
  }
  return false;
}

function contains(container: JsonValue, item: JsonValue): boolean {
  if (typeof container === "string" && typeof item === "string") {
    return container.includes(item);
  }
  if (Array.isArray(container)) {
    return container.some((entry) => deepEqual(entry, item));
  }
  return false;
}

function deepEqual(left: JsonValue, right: JsonValue): boolean {
  if (left === right) return true;
  if (Array.isArray(left) && Array.isArray(right)) {
    return (
      left.length === right.length &&
      left.every((value, index) => deepEqual(value, right[index] as JsonValue))
    );
  }
  if (isRecord(left) && isRecord(right)) {
    const leftKeys = Object.keys(left);
    const rightKeys = Object.keys(right);
    return (
      leftKeys.length === rightKeys.length &&
      leftKeys.every(
        (key) =>
          Object.hasOwn(right, key) &&
          deepEqual(left[key] as JsonValue, right[key] as JsonValue),
      )
    );
  }
  return false;
}