/**
 * Generates the OpenAPI spec from the Fastify app and writes it to disk.
 *
 * Usage:
 *   tsx scripts/generate-openapi.ts [--yaml]
 */
import { writeFileSync } from 'fs';
import { buildServer } from '../src/api/server.js';

const yaml = process.argv.includes('--yaml');

async function generate() {
	const server = await buildServer();
	await server.ready();

	const spec = server.swagger({ yaml });
	const outFile = yaml
		? './llm-gateway-service.openapi.yaml'
		: './llm-gateway-service.openapi.json';
	const content = yaml
		? (spec as unknown as string)
		: JSON.stringify(spec, null, 2);

	writeFileSync(outFile, content + '\n');

	await server.close();
	console.log(`OpenAPI spec written to ${outFile}`);
}

generate();
