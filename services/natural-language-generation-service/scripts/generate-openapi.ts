import { mkdir, writeFile } from 'node:fs/promises';
import { format, resolveConfig } from 'prettier';
import { buildServer } from '../src/api/server.js';

const output = 'openapi/openapi.json';
const server = await buildServer();
await server.ready();
await mkdir('openapi', { recursive: true });
const prettierConfig = (await resolveConfig(output)) ?? {};
const document = await format(JSON.stringify(server.swagger()), {
	...prettierConfig,
	filepath: output,
});
await writeFile(output, document, 'utf8');
await server.close();
process.stdout.write(`OpenAPI specification written to ${output}\n`);
