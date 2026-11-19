import {
  createServer,
  type IncomingMessage,
  type Server,
  type ServerResponse,
} from "node:http";
import { pathToFileURL } from "node:url";
import { ControlError } from "./errors.js";
import { type Mode, runEnvelope } from "./envelope.js";
import { OPENAPI_SPEC, SERVICE_NAME, SERVICE_VERSION } from "./openapi.js";

const MAX_BODY_BYTES = 1_048_576;

export function createControlServer(): Server {
  return createServer((request, response) => {
    void handle(request, response);
  });
}

async function handle(
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    if (request.method === "GET" && request.url === "/health") {
      send(response, 200, {
        status: "ok",
        service: SERVICE_NAME,
        version: SERVICE_VERSION,
      });
      return;
    }
    if (request.method === "GET" && request.url === "/openapi.json") {
      send(response, 200, OPENAPI_SPEC);
      return;
    }
    const mode = modeOf(request.url);
    if (request.method === "POST" && mode) {
      const envelope = await readJson(request);
      try {
        send(response, 200, runEnvelope(mode, envelope));
      } catch (error) {
        if (!(error instanceof ControlError)) throw error;
        if (error.code === "INVALID_ENVELOPE") {
          send(response, 400, {
            error: { code: error.code, message: error.message },
          });
        } else if (mode === "control") {
          send(response, 422, {
            fail: {
              code: error.code,
              message: error.message,
              retryable: error.retryable,
            },
          });
        } else {
          send(response, 422, {
            error: { code: error.code, message: error.message },
          });
        }
      }
      return;
    }
    send(response, 404, { error: { code: "NOT_FOUND", message: "Not found" } });
  } catch (error) {
    const status = error instanceof HttpError ? error.status : 500;
    send(response, status, {
      error: {
        code: error instanceof HttpError ? error.code : "INTERNAL_ERROR",
        message:
          error instanceof HttpError
            ? error.message
            : "Workflow control evaluation failed",
      },
    });
  }
}

function modeOf(url: string | undefined): Mode | undefined {
  if (url === "/control") return "control";
  if (url === "/collect") return "collect";
  return undefined;
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > MAX_BODY_BYTES) {
      throw new HttpError(413, "BODY_TOO_LARGE", "Request body is too large");
    }
    chunks.push(buffer);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown;
  } catch {
    throw new HttpError(400, "INVALID_JSON", "Request body is not valid JSON");
  }
}

function send(response: ServerResponse, status: number, value: unknown): void {
  const body = `${JSON.stringify(value)}\n`;
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
  });
  response.end(body);
}

class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

const entry = process.argv[1];
if (entry && import.meta.url === pathToFileURL(entry).href) {
  const port = Number(process.env.PORT ?? 3000);
  const host = process.env.HOST ?? "0.0.0.0";
  createControlServer().listen(port, host, () => {
    process.stdout.write(
      `${JSON.stringify({ event: "listening", service: SERVICE_NAME, host, port })}\n`,
    );
  });
}