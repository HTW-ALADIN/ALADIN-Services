import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const cli = fileURLToPath(new URL("../build/cli.js", import.meta.url));
const directory = mkdtempSync(join(tmpdir(), "workflow-control-"));

after(() => rmSync(directory, { recursive: true, force: true }));

function run(args, options = {}) {
  return spawnSync(process.execPath, [cli, ...args], {
    encoding: "utf8",
    ...options,
  });
}

describe("CLI", () => {
  it("writes branch operations to a file", () => {
    const input = join(directory, "branch-input.json");
    const output = join(directory, "branch-output.json");
    writeFileSync(
      input,
      JSON.stringify({
        params: {
          kind: "branch",
          cases: [
            {
              when: {
                op: "eq",
                left: { from: "data", path: "$.answer" },
                right: { from: "literal", value: "yes" },
              },
              block: "yes",
            },
          ],
          elseBlock: "no",
        },
        data: { answer: "yes" },
      }),
    );
    const result = run(["control", input, output]);
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(readFileSync(output, "utf8")), {
      push: [{ op: "call", block: "yes" }],
    });
  });

  it("renders semantic control errors as a fail operation", () => {
    const input = join(directory, "bad-params.json");
    const output = join(directory, "bad-params-output.json");
    writeFileSync(
      input,
      JSON.stringify({ params: { kind: "forEach", over: "x" }, data: {} }),
    );
    const result = run(["control", input, output]);
    assert.equal(result.status, 0, result.stderr);
    const failed = JSON.parse(readFileSync(output, "utf8"));
    assert.equal(failed.fail.code, "INVALID_PARAMS");
    assert.equal(failed.fail.retryable, false);
    assert.equal(typeof failed.fail.message, "string");
  });

  it("collects results and supports stdin/stdout", () => {
    const envelope = JSON.stringify({
      params: { kind: "collect", order: ["0"] },
      joined: { slots: { "0": { payload: { result: "ok" } } } },
    });
    const result = run(["collect", "-"], { input: envelope });
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout), ["ok"]);
  });

  it("fails on malformed input, missing files and bad arguments", () => {
    const malformed = join(directory, "malformed.json");
    writeFileSync(malformed, "{");
    assert.equal(run(["control", malformed]).status, 1);
    assert.equal(run(["control", join(directory, "missing.json")]).status, 1);
    assert.equal(run([]).status, 1);
    assert.equal(run(["unknown", malformed]).status, 1);
    assert.equal(run(["control", malformed, "out", "extra"]).status, 1);
    assert.equal(run(["control", malformed, "/no/such/dir/out.json"]).status, 1);
  });

  it("rejects invalid envelopes", () => {
    const input = join(directory, "envelope.json");
    writeFileSync(input, JSON.stringify({ params: { kind: "branch", cases: [] }, extra: true }));
    const result = run(["control", input]);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /accepts only params and data/);
  });
});