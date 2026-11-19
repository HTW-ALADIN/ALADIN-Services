/**
 * Local structural mirrors of the `@aladin/contracts` control types.
 * The image intentionally has no runtime dependency on the Aladin workspace;
 * keep these in sync with `aladin-contracts/src/control.ts` and `dsl.ts`.
 */

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | JsonObject;

export interface JsonObject {
  [key: string]: JsonValue;
}

export type JsonPath = string;

export type Expression =
  | Binding
  | { op: "not"; value: Expression }
  | { op: "and" | "or"; values: Expression[] }
  | {
      op: "eq" | "ne" | "gt" | "gte" | "lt" | "lte";
      left: Expression;
      right: Expression;
    }
  | { op: "contains" | "in"; left: Expression; right: Expression }
  | { op: "get"; from: Expression; path: JsonPath };

export type Binding =
  | { from: "literal"; value: JsonValue }
  | { from: "param"; name: string }
  | {
      from: "item";
      source: "stimuli" | "solutions" | "metaData";
      path?: JsonPath;
    }
  | { from: "data"; path: JsonPath }
  | { from: "session"; key: string; path?: JsonPath }
  | { from: "element"; name?: string; path?: JsonPath };

export type ControlParams =
  | {
      kind: "branch";
      cases: { when: Expression; block: string }[];
      elseBlock?: string;
    }
  | {
      kind: "forEach";
      over: JsonPath;
      as: string;
      concurrency: number;
      bodyBlock: string;
    }
  | {
      kind: "collect";
      order: string[];
      output?: string;
    };

export interface StackOperations {
  push?: InstructionSpec[];
  set?: JsonObject;
  fail?: { code: string; message: string; retryable?: boolean };
}

/** A compiler-produced instruction spec; the runner assigns runtime IDs. */
export interface InstructionSpec {
  op: string;
  [key: string]: JsonValue | undefined;
}

/** One child result as exposed by a join. */
export interface JoinedChild {
  payload?: JsonValue;
  error?: { class?: string; code?: string; message?: string };
}

export interface JoinedState {
  slots: Record<string, JoinedChild>;
}