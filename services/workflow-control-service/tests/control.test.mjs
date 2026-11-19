import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  collectResults,
  MAX_ITEMS,
  runControl,
} from "../build/control.js";
import { evaluateExpression } from "../build/expression.js";
import { parseJsonPath, readJsonPath } from "../build/jsonpath.js";

const branch = (overrides = {}) => ({
  kind: "branch",
  cases: [{ when: { from: "literal", value: true }, block: "case-a" }],
  ...overrides,
});

const forEach = (overrides = {}) => ({
  kind: "forEach",
  over: "$.items",
  as: "item",
  concurrency: 2,
  bodyBlock: "body",
  ...overrides,
});

const collect = (overrides = {}) => ({
  kind: "collect",
  order: ["0", "1"],
  ...overrides,
});

describe("JSONPath subset", () => {
  it("reads dot, bracket and index segments", () => {
    const data = { a: { b: [10, { c: true }] }, "odd key": 1 };
    assert.equal(readJsonPath(data, "$.a.b[1].c"), true);
    assert.equal(readJsonPath(data, '$["odd key"]'), 1);
    assert.equal(readJsonPath(data, "$.a.b[0]"), 10);
    assert.equal(readJsonPath(data, "$"), data);
  });

  it("returns undefined for missing segments and blocks prototype reads", () => {
    assert.equal(readJsonPath({ a: 1 }, "$.a.b"), undefined);
    assert.equal(readJsonPath([], "$[0]"), undefined);
    assert.equal(readJsonPath({}, "$.toString"), undefined);
    assert.equal(readJsonPath(null, "$.a"), undefined);
  });

  it("rejects unsupported or malformed paths", () => {
    for (const path of ["a", "$.a[", "$.a[*]", "$..a", "$.a[-1]", "$.a[01]"]) {
      assert.throws(() => parseJsonPath(path), { code: "INVALID_PATH" });
    }
    assert.throws(() => parseJsonPath(`$.${"a.".repeat(70)}a`), {
      code: "INVALID_PATH",
    });
  });
});

describe("expression evaluator", () => {
  const data = {
    answer: "SELECT 1",
    rows: [1, 2, 3],
    nested: { value: 5 },
    empty: null,
  };

  it("evaluates bindings and comparison operations", () => {
    assert.equal(
      evaluateExpression({ from: "data", path: "$.answer" }, data),
      "SELECT 1",
    );
    assert.equal(
      evaluateExpression({ from: "data", path: "$.missing" }, data),
      null,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "eq",
          left: { from: "data", path: "$.nested.value" },
          right: { from: "literal", value: 5 },
        },
        data,
      ),
      true,
    );
    assert.equal(
      evaluateExpression(
        { op: "ne", left: { from: "literal", value: 1 }, right: { from: "literal", value: 1 } },
        data,
      ),
      false,
    );
  });

  it("evaluates ordered comparisons for numbers and strings only", () => {
    const compare = (op, left, right) =>
      evaluateExpression(
        { op, left: { from: "literal", value: left }, right: { from: "literal", value: right } },
        data,
      );
    assert.equal(compare("gt", 2, 1), true);
    assert.equal(compare("gte", 2, 2), true);
    assert.equal(compare("lt", "a", "b"), true);
    assert.equal(compare("lte", "b", "b"), true);
    assert.equal(compare("gt", 1, "2"), false);
  });

  it("evaluates logical, containment and get operations", () => {
    assert.equal(
      evaluateExpression({ op: "and", values: [] }, data),
      true,
    );
    assert.equal(
      evaluateExpression({ op: "or", values: [] }, data),
      false,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "and",
          values: [
            { from: "literal", value: 1 },
            { from: "literal", value: "x" },
          ],
        },
        data,
      ),
      true,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "or",
          values: [
            { from: "literal", value: 0 },
            { from: "literal", value: "" },
          ],
        },
        data,
      ),
      false,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "contains",
          left: { from: "data", path: "$.answer" },
          right: { from: "literal", value: "SELECT" },
        },
        data,
      ),
      true,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "contains",
          left: { from: "data", path: "$.rows" },
          right: { from: "literal", value: 2 },
        },
        data,
      ),
      true,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "in",
          left: { from: "literal", value: 2 },
          right: { from: "data", path: "$.rows" },
        },
        data,
      ),
      true,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "contains",
          left: { from: "literal", value: 1 },
          right: { from: "literal", value: 1 },
        },
        data,
      ),
      false,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "get",
          from: { from: "data", path: "$.nested" },
          path: "$.value",
        },
        data,
      ),
      5,
    );
    assert.equal(
      evaluateExpression(
        {
          op: "get",
          from: { from: "data", path: "$.nested" },
          path: "$.missing",
        },
        data,
      ),
      null,
    );
  });

  it("rejects unsupported bindings and malformed expressions", () => {
    for (const from of ["param", "item", "session", "element"]) {
      assert.throws(
        () => evaluateExpression({ from, name: "x" }, data),
        { code: "UNSUPPORTED_BINDING" },
      );
    }
    assert.throws(() => evaluateExpression({ from: "other" }, data), {
      code: "INVALID_BINDING",
    });
    assert.throws(() => evaluateExpression({ from: "data" }, data), {
      code: "INVALID_BINDING",
    });
    assert.throws(() => evaluateExpression({ from: "literal" }, data), {
      code: "INVALID_BINDING",
    });
    assert.throws(() => evaluateExpression({ op: "unknown" }, data), {
      code: "INVALID_EXPRESSION",
    });
    assert.throws(() => evaluateExpression({ op: "eq", left: {} }, data), {
      code: "INVALID_EXPRESSION",
    });
    assert.throws(() => evaluateExpression({ op: "get", from: {} }, data), {
      code: "INVALID_EXPRESSION",
    });
    assert.throws(() => evaluateExpression({ op: "and", values: "x" }, data), {
      code: "INVALID_EXPRESSION",
    });
    assert.throws(() => evaluateExpression("x", data), {
      code: "INVALID_EXPRESSION",
    });
    assert.throws(() => evaluateExpression({}, data), {
      code: "INVALID_EXPRESSION",
    });
    assert.throws(
      () =>
        evaluateExpression(
          { op: "eq", left: { from: "literal", value: 1 }, right: { from: "literal", value: 1 }, extra: true },
          data,
        ),
      { code: "INVALID_EXPRESSION" },
    );
    assert.throws(
      () => evaluateExpression({ from: "data", path: "$.a", extra: 1 }, data),
      { code: "INVALID_EXPRESSION" },
    );
  });

  it("enforces depth and node budgets", () => {
    let expression = { from: "literal", value: true };
    for (let index = 0; index < 70; index += 1) {
      expression = { op: "not", value: expression };
    }
    assert.throws(() => evaluateExpression(expression, data), {
      code: "EXPRESSION_TOO_DEEP",
    });
  });
});

describe("branch control", () => {
  const data = { answer: "SELECT 1" };

  it("selects the first matching case, else block or a no-op", () => {
    assert.deepEqual(
      runControl(
        {
          kind: "branch",
          cases: [
            { when: { from: "literal", value: false }, block: "case-a" },
            { when: { from: "literal", value: true }, block: "case-b" },
          ],
          elseBlock: "fallback",
        },
        data,
      ),
      { push: [{ op: "call", block: "case-b" }] },
    );
    assert.deepEqual(
      runControl(
        {
          kind: "branch",
          cases: [{ when: { from: "literal", value: false }, block: "case-a" }],
          elseBlock: "fallback",
        },
        data,
      ),
      { push: [{ op: "call", block: "fallback" }] },
    );
    assert.deepEqual(
      runControl(
        {
          kind: "branch",
          cases: [{ when: { from: "literal", value: false }, block: "case-a" }],
        },
        data,
      ),
      {},
    );
  });

  it("rejects malformed params", () => {
    const invalid = [
      {},
      { kind: "other" },
      branch({ cases: "x" }),
      branch({ cases: [{ block: "b" }] }),
      branch({ cases: [{ when: { from: "literal", value: true }, block: "1 bad" }] }),
      branch({ elseBlock: "bad block" }),
      branch({ extra: true }),
    ];
    for (const params of invalid) {
      assert.throws(() => runControl(params, data), { code: "INVALID_PARAMS" });
    }
    assert.throws(() => runControl(branch(), []), { code: "INVALID_INPUT" });
  });
});

describe("forEach control", () => {
  const data = { items: [{ id: 1 }, { id: 2 }], base: "x" };

  it("pushes a spawn group followed by a join", () => {
    assert.deepEqual(runControl(forEach(), data), {
      push: [
        { op: "join" },
        {
          op: "spawn",
          block: "body",
          slot: "0",
          input: {
            type: "value",
            payload: { items: data.items, base: "x", item: { id: 1 } },
          },
        },
        {
          op: "spawn",
          block: "body",
          slot: "1",
          input: {
            type: "value",
            payload: { items: data.items, base: "x", item: { id: 2 } },
          },
        },
      ],
    });
  });

  it("is a no-op for empty arrays", () => {
    assert.deepEqual(runControl(forEach(), { items: [] }), {});
  });

  it("accepts the utility fan-out boundary and rejects one more item", () => {
    const items = Array.from({ length: MAX_ITEMS }, (_, index) => index);
    const result = runControl(forEach({ concurrency: MAX_ITEMS }), { items });
    assert.equal(result.push.length, MAX_ITEMS + 1);
    assert.throws(
      () =>
        runControl(forEach({ concurrency: MAX_ITEMS }), {
          items: [...items, MAX_ITEMS],
        }),
      { code: "FAN_OUT_LIMIT" },
    );
  });

  it("fails closed when the item count exceeds the concurrency bound", () => {
    assert.throws(
      () =>
        runControl(forEach({ concurrency: 2 }), {
          items: [1, 2, 3],
        }),
      { code: "UNSUPPORTED_CONCURRENCY" },
    );
    assert.equal(
      runControl(forEach({ concurrency: 3 }), { items: [1, 2, 3] }).push
        .length,
      4,
    );
  });

  it("rejects missing, invalid, oversized and amplified inputs", () => {
    assert.throws(() => runControl(forEach(), {}), { code: "INVALID_INPUT" });
    assert.throws(() => runControl(forEach(), { items: "x" }), {
      code: "INVALID_INPUT",
    });
    assert.throws(
      () => runControl(forEach(), { items: [], big: "x".repeat(1_100_000) }),
      { code: "INPUT_LIMIT" },
    );
    assert.throws(
      () =>
        runControl(forEach({ concurrency: 6 }), {
          items: [1, 2, 3, 4, 5, 6],
          blob: "x".repeat(900_000),
        }),
      { code: "INPUT_LIMIT" },
    );
  });

  it("rejects malformed params", () => {
    const invalid = [
      forEach({ over: "" }),
      forEach({ as: "1bad" }),
      forEach({ concurrency: 0 }),
      forEach({ concurrency: 1.5 }),
      forEach({ concurrency: MAX_ITEMS + 1 }),
      forEach({ bodyBlock: "bad block" }),
      forEach({ extra: true }),
    ];
    for (const params of invalid) {
      assert.throws(() => runControl(params, data), { code: "INVALID_PARAMS" });
    }
  });
});

describe("collect", () => {
  const joined = {
    slots: {
      "0": { payload: { result: 1 } },
      "1": { payload: { result: 2 } },
    },
  };

  it("returns outputs in declared order", () => {
    assert.deepEqual(collectResults(collect(), joined), [1, 2]);
    assert.deepEqual(
      collectResults(collect({ order: ["1", "0"] }), joined),
      [2, 1],
    );
    assert.deepEqual(
      collectResults(collect({ output: "result" }), joined),
      [1, 2],
    );
  });

  it("supports sole-output and scalar payloads", () => {
    assert.deepEqual(
      collectResults(collect({ order: ["a"] }), {
        slots: { a: { payload: { only: "value" } } },
      }),
      ["value"],
    );
    assert.deepEqual(
      collectResults(collect({ order: ["a"] }), {
        slots: { a: { payload: 42 } },
      }),
      [42],
    );
    assert.deepEqual(collectResults(collect({ order: [] }), { slots: {} }), []);
  });

  it("rejects missing, failed, ambiguous and unresolved children", () => {
    assert.throws(() => collectResults(collect(), { slots: {} }), {
      code: "MISSING_SLOT",
    });
    assert.throws(
      () =>
        collectResults(collect({ order: ["a"] }), {
          slots: { a: { error: { code: "X" } } },
        }),
      { code: "CHILD_FAILED" },
    );
    assert.throws(
      () =>
        collectResults(collect({ order: ["a"] }), {
          slots: { a: { payload: { one: 1, two: 2 } } },
        }),
      { code: "AMBIGUOUS_OUTPUT" },
    );
    assert.throws(
      () =>
        collectResults(collect({ order: ["a"], output: "missing" }), {
          slots: { a: { payload: { one: 1 } } },
        }),
      { code: "MISSING_OUTPUT" },
    );
    assert.throws(
      () =>
        collectResults(collect({ order: ["a"] }), {
          slots: { a: { payload: "redis://ref" } },
        }),
      { code: "UNRESOLVED_JOINED_PAYLOAD" },
    );
    assert.throws(() => collectResults(collect(), { slots: [] }), {
      code: "INVALID_JOINED",
    });
    assert.throws(
      () => collectResults(collect(), { slots: { "0": "x" } }),
      { code: "INVALID_JOINED" },
    );
    assert.throws(
      () => collectResults(collect({ order: ["0"] }), { slots: {} }),
      { code: "MISSING_SLOT" },
    );
  });

  it("rejects collect params in control mode and vice versa", () => {
    assert.throws(() => runControl(collect(), {}), { code: "INVALID_MODE" });
    assert.throws(() => collectResults(branch(), { slots: {} }), {
      code: "INVALID_MODE",
    });
    for (const params of [
      collect({ order: "x" }),
      collect({ order: [1] }),
      collect({ order: ["a", "a"] }),
      collect({ output: "1bad" }),
      collect({ extra: true }),
    ]) {
      assert.throws(() => collectResults(params, { slots: {} }), {
        code: "INVALID_PARAMS",
      });
    }
  });
});