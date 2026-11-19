import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { createControlServer } from "../build/server.js";

let server;
let base;

before(async () => {
  server = createControlServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  base = `http://127.0.0.1:${address.port}`;
});

after(async () => {
  await new Promise((resolve) => server.close(resolve));
});

describe("HTTP surface", () => {
  it("reports health and OpenAPI", async () => {
    const health = await fetch(`${base}/health`);
    assert.equal(health.status, 200);
    assert.deepEqual(await health.json(), {
      status: "ok",
      service: "workflow-control-service",
      version: "0.1.0",
    });
    const openapi = await fetch(`${base}/openapi.json`);
    assert.equal(openapi.status, 200);
    assert.equal((await openapi.json()).info.title, "workflow-control-service");
  });

  it("evaluates control and collect requests", async () => {
    const control = await fetch(`${base}/control`, {
      method: "POST",
      body: JSON.stringify({
        params: {
          kind: "branch",
          cases: [{ when: { from: "literal", value: true }, block: "a" }],
        },
        data: {},
      }),
    });
    assert.equal(control.status, 200);
    assert.deepEqual(await control.json(), {
      push: [{ op: "call", block: "a" }],
    });

    const collected = await fetch(`${base}/collect`, {
      method: "POST",
      body: JSON.stringify({
        params: { kind: "collect", order: ["0"] },
        joined: { slots: { "0": { payload: { result: [] } } } },
      }),
    });
    assert.equal(collected.status, 200);
    assert.deepEqual(await collected.json(), [[]]);
  });

  it("maps domain and protocol errors", async () => {
    const control = await fetch(`${base}/control`, {
      method: "POST",
      body: JSON.stringify({ params: { kind: "branch", cases: "x" }, data: {} }),
    });
    assert.equal(control.status, 422);
    assert.equal((await control.json()).fail.code, "INVALID_PARAMS");

    const collected = await fetch(`${base}/collect`, {
      method: "POST",
      body: JSON.stringify({
        params: { kind: "collect", order: ["0"] },
        joined: { slots: {} },
      }),
    });
    assert.equal(collected.status, 422);
    assert.equal((await collected.json()).error.code, "MISSING_SLOT");

    const malformed = await fetch(`${base}/control`, {
      method: "POST",
      body: "{",
    });
    assert.equal(malformed.status, 400);

    const missing = await fetch(`${base}/missing`);
    assert.equal(missing.status, 404);
  });

  it("rejects invalid envelopes and oversized bodies", async () => {
    const invalid = await fetch(`${base}/control`, {
      method: "POST",
      body: JSON.stringify({
        params: { kind: "branch", cases: [] },
        data: {},
        extra: true,
      }),
    });
    assert.equal(invalid.status, 400);

    const oversized = await fetch(`${base}/control`, {
      method: "POST",
      body: JSON.stringify({
        params: { kind: "branch", cases: [] },
        data: { blob: "x".repeat(1_100_000) },
      }),
    });
    assert.equal(oversized.status, 413);
  });
});