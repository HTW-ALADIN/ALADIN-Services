export const SERVICE_NAME = "workflow-control-service";
export const SERVICE_VERSION = "0.1.0";

export const OPENAPI_SPEC = {
  openapi: "3.1.0",
  info: {
    title: SERVICE_NAME,
    version: SERVICE_VERSION,
    description:
      "Official Aladin workflow control image: branch/forEach stack operations and ordered result collection.",
  },
  paths: {
    "/health": {
      get: {
        operationId: "health",
        responses: { "200": { description: "Service is ready" } },
      },
    },
    "/control": {
      post: {
        operationId: "control",
        summary: "Evaluate branch/forEach params into StackOperations",
        requestBody: { required: true },
        responses: {
          "200": { description: "Stack operations" },
          "400": { description: "Malformed request" },
          "422": { description: "Control failure returned as a fail operation" },
        },
      },
    },
    "/collect": {
      post: {
        operationId: "collect",
        summary: "Collect ordered join slots into a JSON array",
        description:
          "Experimental: requires the runtime to materialize joined child results. The current runner does not expose joined slots to a follow-up step yet.",
        requestBody: { required: true },
        responses: {
          "200": { description: "Ordered child outputs" },
          "400": { description: "Malformed request" },
          "422": { description: "Collection failure" },
        },
      },
    },
  },
} as const;