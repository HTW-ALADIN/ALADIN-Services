import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { ControlError } from "./errors.js";
import { runEnvelope } from "./envelope.js";

function usage(): never {
  process.stderr.write(
    "Usage: workflow-control <control|collect> <input.json|-> [output.json|-]\n",
  );
  process.exit(1);
}

function readInput(path: string): unknown {
  let raw: string;
  try {
    raw =
      path === "-"
        ? readFileSync(0, "utf8")
        : readFileSync(resolve(path), "utf8");
  } catch {
    throw new ControlError("INPUT_UNREADABLE", "Input file could not be read");
  }
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    throw new ControlError("INVALID_JSON", "Input is not valid JSON");
  }
}

function writeOutput(path: string | undefined, value: unknown): void {
  const text = `${JSON.stringify(value)}\n`;
  if (path === undefined || path === "-") {
    process.stdout.write(text);
    return;
  }
  try {
    writeFileSync(resolve(path), text, "utf8");
  } catch {
    throw new ControlError(
      "OUTPUT_UNWRITABLE",
      "Output file could not be written",
    );
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length < 2 || args.includes("-h") || args.includes("--help")) {
    usage();
  }
  const mode = args[0];
  if (mode !== "control" && mode !== "collect") usage();
  if (args.length > 3) usage();
  const input = args[1] as string;
  const output = args[2];
  const envelope = readInput(input);
  try {
    writeOutput(output, runEnvelope(mode, envelope));
  } catch (error) {
    if (
      mode === "control" &&
      error instanceof ControlError &&
      error.code !== "INVALID_ENVELOPE"
    ) {
      writeOutput(output, {
        fail: {
          code: error.code,
          message: error.message,
          retryable: error.retryable,
        },
      });
      return;
    }
    throw error;
  }
}

try {
  main();
} catch (error) {
  const message =
    error instanceof ControlError
      ? error.message
      : "Workflow control evaluation failed";
  process.stderr.write(`${message}\n`);
  process.exit(1);
}