import { ControlError } from "./errors.js";

export type PathSegment = string | number;

const MAX_PATH_LENGTH = 512;
const MAX_SEGMENTS = 64;
const NAME_START = /[A-Za-z_$]/;
const NAME_REST = /[A-Za-z0-9_$]/;

/**
 * Parses the JSONPath subset used by the workflow DSL: `$`, `.name`,
 * `["name"]`, and `[0]`. Filters, wildcards and recursive descent are rejected
 * so evaluation stays bounded and predictable.
 */
export function parseJsonPath(path: string): PathSegment[] {
  if (
    typeof path !== "string" ||
    !path.startsWith("$") ||
    path.length > MAX_PATH_LENGTH
  ) {
    throw new ControlError("INVALID_PATH", "JSONPath is invalid");
  }
  const segments: PathSegment[] = [];
  let index = 1;
  while (index < path.length) {
    const character = path.charAt(index);
    if (character === ".") {
      index += 1;
      if (!NAME_START.test(path.charAt(index))) {
        throw new ControlError("INVALID_PATH", "JSONPath is invalid");
      }
      const start = index;
      index += 1;
      while (index < path.length && NAME_REST.test(path.charAt(index))) {
        index += 1;
      }
      segments.push(path.slice(start, index));
    } else if (character === "[") {
      index += 1;
      if (path.charAt(index) === '"') {
        index += 1;
        let name = "";
        while (index < path.length && path.charAt(index) !== '"') {
          if (path.charAt(index) === "\\") {
            index += 1;
            if (index >= path.length) {
              throw new ControlError("INVALID_PATH", "JSONPath is invalid");
            }
          }
          name += path.charAt(index);
          index += 1;
        }
        if (path.charAt(index) !== '"' || path.charAt(index + 1) !== "]") {
          throw new ControlError("INVALID_PATH", "JSONPath is invalid");
        }
        index += 2;
        segments.push(name);
      } else {
        const start = index;
        while (index < path.length && path.charAt(index) !== "]") index += 1;
        const raw = path.slice(start, index);
        if (
          path.charAt(index) !== "]" ||
          !/^(?:0|[1-9]\d*)$/.test(raw)
        ) {
          throw new ControlError("INVALID_PATH", "JSONPath is invalid");
        }
        index += 1;
        segments.push(Number(raw));
      }
    } else {
      throw new ControlError("INVALID_PATH", "JSONPath is invalid");
    }
    if (segments.length > MAX_SEGMENTS) {
      throw new ControlError("INVALID_PATH", "JSONPath is too deep");
    }
  }
  return segments;
}

/** Reads own properties only; a missing segment returns `undefined`. */
export function readJsonPath(value: unknown, path: string): unknown {
  let current: unknown = value;
  for (const segment of parseJsonPath(path)) {
    if (typeof segment === "number") {
      if (!Array.isArray(current) || segment >= current.length) return undefined;
      current = current[segment];
      continue;
    }
    if (
      current === null ||
      typeof current !== "object" ||
      Array.isArray(current) ||
      !Object.hasOwn(current, segment)
    ) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return current;
}