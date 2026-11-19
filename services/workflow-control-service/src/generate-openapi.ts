import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { OPENAPI_SPEC, SERVICE_NAME } from "./openapi.js";

const path = resolve(`${SERVICE_NAME}.openapi.json`);
writeFileSync(path, `${JSON.stringify(OPENAPI_SPEC, null, 2)}\n`, "utf8");
process.stdout.write(`${path}\n`);